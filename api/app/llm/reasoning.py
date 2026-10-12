"""Remove reasoning text from model output and pull JSON out of what is left."""

import json
import re
from typing import Any

_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def strip_reasoning(text: str | None) -> str:
    """Drop <think> blocks: complete ones, a lone closing tag, or a cut-off block."""
    if not text:
        return ""
    text = _BLOCK.sub("", text)
    if "</think>" in text:  # the chat template opened the block for the model
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text:  # truncated before the block closed
        text = text.split("<think>", 1)[0]
    return text.strip()


def extract_json(text: str) -> Any:
    """Return the first JSON object or array in text (fenced or inline)."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return decoder.raw_decode(text, i)[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON found in model reply")
