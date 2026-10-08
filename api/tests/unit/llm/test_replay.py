"""Record/replay transport: record once against a fake server, replay with no network."""

import asyncio
import functools
import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.llm.client import LLMClient
from app.llm.errors import ModelUnavailable
from app.llm.registry import Registry
from app.llm.replay import MissingFixture, ReplayTransport, replay_client
from tests.unit.llm.conftest import FakeServer, completion

SECRET = "sk-super-secret-key"


def sync(fn: Callable[..., Coroutine[Any, Any, None]]) -> Callable[..., None]:
    """No async pytest plugin here: run each async test with asyncio.run."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        asyncio.run(fn(*args, **kwargs))

    return wrapper


def _client(registry: Registry, http: httpx.AsyncClient, key: str = "x") -> LLMClient:
    return LLMClient(registry, api_key=key, http_client=http)


def _recorder(tmp: Path, server: FakeServer) -> httpx.AsyncClient:
    inner = httpx.MockTransport(server.handle)
    return httpx.AsyncClient(transport=ReplayTransport("record", tmp, inner=inner))


@sync
async def test_record_then_replay_same_text(registry: Registry, tmp_path: Path) -> None:
    server = FakeServer().ok(completion("four"))
    first = await _client(registry, _recorder(tmp_path, server)).chat(
        "router", [{"role": "user", "content": "2+2?"}]
    )
    replayer = httpx.AsyncClient(transport=ReplayTransport("replay", tmp_path))
    second = await _client(registry, replayer).chat(
        "router", [{"role": "user", "content": "2+2?"}]
    )
    assert first.text == second.text == "four"
    assert len(server.requests) == 1


@sync
async def test_replay_different_prompt_is_missing_fixture(
    registry: Registry, tmp_path: Path
) -> None:
    await _client(registry, _recorder(tmp_path, FakeServer().ok(completion()))).chat(
        "router", [{"role": "user", "content": "a"}]
    )
    transport = ReplayTransport("replay", tmp_path)
    other = httpx.Request("POST", "https://tf.test/v1/chat/completions", json={"x": 1})
    with pytest.raises(MissingFixture, match="TF_RECORD=1"):
        await transport.handle_async_request(other)

    # Through LLMClient the SDK wraps the error as a connection error, which the
    # client retries and then reports as ModelUnavailable. No network either way.
    async def no_sleep(_: float) -> None:
        return None

    client = LLMClient(
        registry,
        api_key="x",
        http_client=httpx.AsyncClient(transport=transport),
        sleep=no_sleep,
    )
    with pytest.raises(ModelUnavailable):
        await client.chat("router", [{"role": "user", "content": "b"}])


@sync
async def test_fixture_has_no_secret_and_is_pretty(
    registry: Registry, tmp_path: Path
) -> None:
    server = FakeServer().ok(completion("hi"))
    await _client(registry, _recorder(tmp_path, server), SECRET).chat(
        "router", [{"role": "user", "content": "q"}]
    )
    files = list(tmp_path.glob("??/*.json"))
    assert len(files) == 1
    text = files[0].read_text()
    assert SECRET not in text and "authorization" not in text.lower()
    assert files[0].parent.name == files[0].stem[:2]
    data = json.loads(text)
    assert text == json.dumps(data, indent=2, sort_keys=True) + "\n"
    assert set(data["response"]["headers"]) <= {"content-type"}
    assert data["request"]["method"] == "POST"
    assert data["request"]["path"].endswith("/chat/completions")


@sync
async def test_error_responses_are_not_recorded(tmp_path: Path) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = ReplayTransport("record", tmp_path, inner=httpx.MockTransport(fail))
    async with httpx.AsyncClient(transport=transport) as http:
        resp = await http.post("https://tf.test/v1/x", json={"a": 1})
    assert resp.status_code == 500
    assert list(tmp_path.glob("**/*.json")) == []


@sync
async def test_key_ignores_headers_host_and_body_key_order(tmp_path: Path) -> None:
    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"v": 1})

    rec = ReplayTransport("record", tmp_path, inner=httpx.MockTransport(ok))
    async with httpx.AsyncClient(transport=rec) as http:
        await http.post("https://a.test/p", json={"a": 1, "b": 2}, headers={"x": "1"})
    rep = ReplayTransport("replay", tmp_path)
    async with httpx.AsyncClient(transport=rep) as http:
        resp = await http.post("https://b.test/p?k=s", content=b'{"b": 2, "a": 1}')
    assert resp.json() == {"v": 1}


def test_replay_client_mode_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TF_RECORD", raising=False)
    assert replay_client(tmp_path)._transport.mode == "replay"  # type: ignore[attr-defined]
    monkeypatch.setenv("TF_RECORD", "1")
    assert replay_client(tmp_path)._transport.mode == "record"  # type: ignore[attr-defined]
