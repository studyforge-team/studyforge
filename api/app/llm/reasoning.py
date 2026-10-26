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


# JSON turns an un-doubled LaTeX "\b \f \t \r \n" into a control char, eating the backslash.
# Undo it: BS/FF always, TAB/CR before a letter, and newline only before a known LaTeX
# command (the table holds what follows the lost "n") and only in text that holds math ($...$),
# so real "\nThe" or "\nu = 3" prose line breaks survive.
_NL_CMD = "u|abla|eq|e|i|otin|ot|onumber|ewline|gtr|less|mid"  # nu nabla neq ne ni ...
_CTRL = re.compile(r"[\x08\x0c]|[\t\r](?=[A-Za-z])")
_CTRL_NL = re.compile(rf"\n(?=(?:{_NL_CMD})(?![A-Za-z]))")
_CTRL_FIX = {"\x08": "\\b", "\x0c": "\\f", "\t": "\\t", "\r": "\\r", "\n": "\\n"}
# Python source is never touched: a real "u = 3\ni = 0" line break must stay a line break.
_CODE_KEYS = frozenset({"code", "key_code"})


def fix_latex_escapes(value: Any) -> Any:
    """Repair LaTeX backslashes JSON decoded as control chars, recursively (never in code fields)."""
    if isinstance(value, str):
        out = _CTRL.sub(lambda m: _CTRL_FIX[m.group()], value)
        if "$" in out:
            out = _CTRL_NL.sub(lambda m: _CTRL_FIX[m.group()], out)
        return out
    if isinstance(value, dict):
        return {k: v if k in _CODE_KEYS else fix_latex_escapes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [fix_latex_escapes(v) for v in value]
    return value


# Single-backslash LaTeX ("\Delta H", "^\circ") is not valid JSON: double every backslash
# that does not start a valid JSON escape (an already-doubled pair is consumed as a pair).
_BAD_ESCAPE = re.compile(r'\\(["\\/bfnrt]|u[0-9a-fA-F]{4})?')


def _double_bad_backslashes(text: str) -> str:
    return _BAD_ESCAPE.sub(lambda m: m.group() if m.group(1) else "\\\\", text)


def extract_json(text: str) -> Any:
    """Return the first JSON object or array in text (fenced or inline)."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    text = _double_bad_backslashes(text)
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return fix_latex_escapes(decoder.raw_decode(text, i)[0])
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON found in model reply")
