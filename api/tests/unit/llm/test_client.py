import asyncio
from typing import Any

import pytest
from conftest import FakeClock, FakeServer, completion
from pydantic import BaseModel

from app.llm.client import LLMClient
from app.llm.cost import InMemoryCostRecorder
from app.llm.errors import (
    BudgetExceeded,
    DeadlineExceeded,
    JSONRepairFailed,
    LLMAuthError,
    LLMRequestError,
    ModelUnavailable,
)
from app.llm.registry import Registry

MSG = [{"role": "user", "content": "hi"}]


def make(
    registry: Registry, server: FakeServer, clock: FakeClock, **kw: Any
) -> tuple[LLMClient, InMemoryCostRecorder]:
    recorder = InMemoryCostRecorder()
    client = LLMClient(
        registry,
        api_key="test",
        http_client=server.http_client(),
        recorder=recorder,
        clock=clock,
        sleep=clock.sleep,
        rng=lambda: 0.0,
        **kw,
    )
    return client, recorder


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_success_logs_one_cost_row(registry: Registry) -> None:
    server, clock = (
        FakeServer().ok(completion("hello", tokens=(1000, 500))),
        FakeClock(),
    )
    client, rec = make(registry, server, clock)
    res = run(client.chat("solver", MSG))
    assert res.text == "hello"
    assert res.model_id == "test/super"
    # 1000 in at $1/M + 500 out at $3/M
    assert res.cost_usd == pytest.approx(0.0025)
    assert len(rec.records) == 1
    row = rec.records[0]
    assert (row.ok, row.role, row.prompt_tokens, row.completion_tokens) == (
        True,
        "solver",
        1000,
        500,
    )
    assert server.body(0)["model"] == "test/super"
    assert server.body(0)["temperature"] == 1.0


def test_reasoning_flag_per_role(registry: Registry) -> None:
    server, clock = FakeServer().ok(completion()).ok(completion()), FakeClock()
    client, _ = make(registry, server, clock)
    run(client.chat("solver", MSG))
    run(client.chat("router", MSG))
    think = [server.body(i)["chat_template_kwargs"]["enable_thinking"] for i in (0, 1)]
    assert think == [True, False]


def test_reasoning_text_kept_out_of_answer(registry: Registry) -> None:
    body = completion("<think>hmm</think>42", reasoning_content="long thoughts")
    server, clock = FakeServer().ok(body), FakeClock()
    client, _ = make(registry, server, clock)
    res = run(client.chat("solver", MSG))
    assert res.text == "42"
    assert res.reasoning == "long thoughts"


def test_429_honours_retry_after(registry: Registry) -> None:
    server = FakeServer().status(429, {"retry-after": "2"}).ok(completion())
    clock = FakeClock()
    client, rec = make(registry, server, clock)
    run(client.chat("solver", MSG))
    assert clock.sleeps == [2.0]
    assert [r.ok for r in rec.records] == [False, True]
    assert rec.records[0].error == "status 429"


def test_three_retries_with_backoff_then_unavailable(registry: Registry) -> None:
    server = FakeServer()
    for _ in range(4):
        server.status(503)
    clock = FakeClock()
    client, rec = make(registry, server, clock)
    with pytest.raises(ModelUnavailable):
        run(client.chat("solver", MSG))  # solver has no fallback model
    assert len(server.requests) == 4
    assert clock.sleeps == [0.5, 1.0, 2.0]
    assert len(rec.records) == 4


def test_timeouts_are_retried(registry: Registry) -> None:
    server, clock = FakeServer().timeout().ok(completion("late")), FakeClock()
    client, _ = make(registry, server, clock)
    assert run(client.chat("solver", MSG)).text == "late"


def test_router_falls_back_to_super(registry: Registry) -> None:
    server = FakeServer()
    for _ in range(4):
        server.status(500)
    server.ok(completion("from super"))
    client, _ = make(registry, server, FakeClock())
    res = run(client.chat("router", MSG))
    assert res.model_id == "test/super"
    assert [server.body(i)["model"] for i in (0, 4)] == ["test/nano", "test/super"]


def test_missing_model_falls_back_without_retry(registry: Registry) -> None:
    server, clock = FakeServer().status(404).ok(completion()), FakeClock()
    client, _ = make(registry, server, clock)
    assert run(client.chat("router", MSG)).model_id == "test/super"
    assert clock.sleeps == []


def test_400_is_not_retried(registry: Registry) -> None:
    server, clock = FakeServer().status(400), FakeClock()
    client, _ = make(registry, server, clock)
    with pytest.raises(LLMRequestError):
        run(client.chat("router", MSG))
    assert len(server.requests) == 1


def test_401_stops_everything(registry: Registry) -> None:
    server, clock = FakeServer().status(401), FakeClock()
    client, _ = make(registry, server, clock)
    with pytest.raises(LLMAuthError):
        run(client.chat("router", MSG))
    assert len(server.requests) == 1


def test_no_call_once_deadline_passed(registry: Registry) -> None:
    server, clock = FakeServer(), FakeClock()
    client, _ = make(registry, server, clock)
    with pytest.raises(DeadlineExceeded):
        run(client.chat("solver", MSG, deadline=clock.now - 1))
    assert server.requests == []


def test_no_retry_when_wait_exceeds_deadline(registry: Registry) -> None:
    server, clock = FakeServer().status(429, {"retry-after": "5"}), FakeClock()
    client, _ = make(registry, server, clock)
    with pytest.raises(DeadlineExceeded):
        run(client.chat("solver", MSG, deadline=clock.now + 3))
    assert clock.sleeps == []


def test_request_timeout_is_capped_by_deadline(registry: Registry) -> None:
    server, clock = FakeServer().ok(completion()).ok(completion()), FakeClock()
    client, _ = make(registry, server, clock)
    run(client.chat("solver", MSG, deadline=clock.now + 12))
    run(client.chat("solver", MSG))
    reads = [r.extensions["timeout"]["read"] for r in server.requests]
    assert reads == [12.0, 60.0]


def test_budget_guard_blocks_before_request(registry: Registry) -> None:
    class Broke:
        async def check(self, role: str, model_id: str) -> None:
            raise BudgetExceeded("cap reached")

    server = FakeServer()
    client, _ = make(registry, server, FakeClock(), budget=Broke())
    with pytest.raises(BudgetExceeded):
        run(client.chat("solver", MSG))
    assert server.requests == []


def test_chat_tools_returns_tool_calls(registry: Registry) -> None:
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "run_python", "arguments": '{"code": "result = {}"}'},
    }
    server = FakeServer().ok(completion(None, tool_calls=[call]))
    client, _ = make(registry, server, FakeClock())
    tools = [{"type": "function", "function": {"name": "run_python", "parameters": {}}}]
    res = run(client.chat_tools("solver", MSG, tools))
    assert [(c.name, c.arguments) for c in res.tool_calls] == [
        ("run_python", '{"code": "result = {}"}')
    ]
    assert server.body(0)["tools"] == tools


class Answer(BaseModel):
    value: float
    unit: str


def test_chat_json_strips_reasoning_and_validates(registry: Registry) -> None:
    body = completion('<think>x</think>```json\n{"value": 2.5, "unit": "m"}\n```')
    server = FakeServer().ok(body)
    client, _ = make(registry, server, FakeClock())
    parsed, _ = run(client.chat_json("solver", MSG, Answer))
    assert parsed == Answer(value=2.5, unit="m")
    # reasoning forced off for JSON calls even though solver has it on
    assert server.body(0)["chat_template_kwargs"]["enable_thinking"] is False


def test_chat_json_repairs_once(registry: Registry) -> None:
    server = FakeServer()
    server.ok(completion('{"value": "lots"}')).ok(
        completion('{"value": 3, "unit": "K"}')
    )
    client, rec = make(registry, server, FakeClock())
    parsed, res = run(client.chat_json("router", MSG, Answer))
    assert parsed.value == 3
    repair = server.body(1)["messages"]
    assert repair[-2] == {"role": "assistant", "content": '{"value": "lots"}'}
    assert "not valid" in repair[-1]["content"]
    assert len(rec.records) == 2
    assert res.cost_usd == pytest.approx(2 * (1000 * 0.1 + 500 * 0.4) / 1e6)


def test_chat_json_gives_up_after_one_repair(registry: Registry) -> None:
    server = FakeServer().ok(completion("nope")).ok(completion("still nope"))
    client, _ = make(registry, server, FakeClock())
    with pytest.raises(JSONRepairFailed):
        run(client.chat_json("router", MSG, Answer))
    assert len(server.requests) == 2


def test_vision_sends_image_part(registry: Registry) -> None:
    server = FakeServer().ok(completion("x = 2"))
    client, _ = make(registry, server, FakeClock())
    res = run(client.vision("data:image/jpeg;base64,AAAA", "Read the question."))
    assert res.text == "x = 2"
    content = server.body(0)["messages"][0]["content"]
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,AAAA"},
    }


def test_missing_key_fails_before_any_request(
    registry: Registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TF_API_KEY", raising=False)
    server = FakeServer()
    client = LLMClient(registry, http_client=server.http_client())
    with pytest.raises(LLMAuthError, match="TF_API_KEY"):
        run(client.chat("solver", MSG))
    assert server.requests == []


def test_vision_sends_no_thinking_flag(registry: Registry) -> None:
    server = FakeServer().ok(completion("x"))
    client, _ = make(registry, server, FakeClock())
    run(client.vision("data:image/png;base64,AA", "Read it."))
    assert "chat_template_kwargs" not in server.body(0)


def test_cut_off_reply_is_reported(registry: Registry) -> None:
    server = FakeServer().ok(completion("result = {", finish_reason="length"))
    client, _ = make(registry, server, FakeClock())
    assert run(client.chat("solver", MSG)).finish_reason == "length"


def test_reply_without_choices_is_unavailable(registry: Registry) -> None:
    body = completion()
    body["choices"] = []
    client, _ = make(registry, FakeServer().ok(body), FakeClock())
    with pytest.raises(ModelUnavailable):
        run(client.chat("solver", MSG))
