"""One real call to Token Factory. Runs only with TF_LIVE=1 and TF_API_KEY set."""

import asyncio
import os

import pytest

from app.llm.client import LLMClient
from app.llm.cost import InMemoryCostRecorder
from app.llm.registry import load_registry

pytestmark = pytest.mark.skipif(
    os.environ.get("TF_LIVE") != "1", reason="set TF_LIVE=1"
)


def test_live_router_call_logs_cost() -> None:
    recorder = InMemoryCostRecorder()
    client = LLMClient(load_registry(), recorder=recorder)
    res = asyncio.run(
        client.chat("router", [{"role": "user", "content": "Reply with the word OK."}])
    )
    assert "ok" in res.text.lower()
    assert recorder.records[-1].ok
    assert recorder.records[-1].prompt_tokens > 0
