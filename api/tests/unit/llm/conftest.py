"""Fakes for LLM client tests: scripted HTTP server, fake clock, test registry."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.llm.registry import Registry, load_registry

TEST_REGISTRY = """
base_url: https://tf.test/v1/
api_key_env: TF_API_KEY
models:
  nano: {id: test/nano, input_usd_per_m: 0.1, output_usd_per_m: 0.4}
  super: {id: test/super, input_usd_per_m: 1.0, output_usd_per_m: 3.0}
  ultra: {id: null}
  vision: {id: test/vision, input_usd_per_m: 0.5, output_usd_per_m: 0.5}
roles:
  router: {models: [nano, super], timeout_s: 20, reasoning: false}
  solver: {models: [super], timeout_s: 60, reasoning: true, temperature: 1.0, top_p: 0.95}
  cross_check: {models: [ultra, super], timeout_s: 60, reasoning: true}
  vision: {models: [vision], timeout_s: 45}
"""


def completion(
    content: str | None = "ok",
    *,
    reasoning_content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    tokens: tuple[int, int] = (1000, 500),
    finish_reason: str = "stop",
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": tokens[0],
            "completion_tokens": tokens[1],
            "total_tokens": sum(tokens),
        },
    }


class FakeServer:
    """Answers each request with the next scripted reply and keeps the requests."""

    def __init__(self) -> None:
        self.replies: list[Callable[[httpx.Request], httpx.Response]] = []
        self.requests: list[httpx.Request] = []

    def ok(self, body: dict[str, Any]) -> "FakeServer":
        self.replies.append(lambda r: httpx.Response(200, json=body))
        return self

    def status(self, code: int, headers: dict[str, str] | None = None) -> "FakeServer":
        err = {"error": {"message": f"status {code}"}}
        self.replies.append(lambda r: httpx.Response(code, json=err, headers=headers))
        return self

    def timeout(self) -> "FakeServer":
        def raise_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        self.replies.append(raise_timeout)
        return self

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.replies.pop(0)(request)

    def body(self, i: int) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(self.requests[i].content)
        return result

    def http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def registry(tmp_path: Path) -> Registry:
    path = tmp_path / "models.yaml"
    path.write_text(TEST_REGISTRY)
    return load_registry(path)
