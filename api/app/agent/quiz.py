"""Quiz schema, validation and answer-key checking (ticket Q1, model-free part).

Numerical answer keys are never written by the model as numbers. The model writes a
``key_code`` script; the browser sandbox runs it and the client calls ``check_key`` and
``fill_solution`` on the result. Nothing here executes model-written code.
"""

import json
import math
import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
# A digit-led token not glued to a preceding word character (so C_A0 and x2 are ignored).
_NUMBER_TOKEN = re.compile(r"(?<!\w)\d[\w.,]*")
_INTEGER = re.compile(r"0|[1-9]\d*")
_FORBIDDEN_KEY_CODE = (
    "import os",
    "import sys",
    "open(",
    "__import__",
    "eval(",
    "exec(",
)
_ZERO_ABS_TOL = 1e-12


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Item(_Strict):
    topic: str = Field(min_length=1, max_length=80)
    source: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=8)
    stem: str = Field(min_length=1)


class MCQItem(_Item):
    type: Literal["mcq"]
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    misconceptions: dict[int, str]
    explanation: str

    @field_validator("options")
    @classmethod
    def _options_ok(cls, v: list[str]) -> list[str]:
        if any(not o.strip() for o in v):
            raise ValueError("options must be non-empty")
        if len({o.strip() for o in v}) != len(v):
            raise ValueError("options must be distinct")
        return v

    @model_validator(mode="after")
    def _misconceptions_ok(self) -> "MCQItem":
        wrong = {0, 1, 2, 3} - {self.correct_index}
        if set(self.misconceptions) != wrong:
            raise ValueError(
                f"misconceptions must have exactly the wrong indices {sorted(wrong)} as keys"
            )
        if any(not m.strip() for m in self.misconceptions.values()):
            raise ValueError("misconceptions texts must be non-empty")
        return self


class NumericalItem(_Item):
    type: Literal["numerical"]
    key_code: str
    unit: str
    tolerance_rel: float = Field(default=0.01, gt=0, le=0.1)
    worked_solution: str

    @field_validator("key_code")
    @classmethod
    def _key_code_lint(cls, v: str) -> str:
        # Cheap lint only; the browser sandbox is the real security boundary.
        if "result =" not in v:
            raise ValueError("key_code must assign 'result ='")
        for bad in _FORBIDDEN_KEY_CODE:
            if bad in v:
                raise ValueError(f"key_code must not contain {bad!r}")
        return v

    @field_validator("worked_solution")
    @classmethod
    def _worked_solution_ok(cls, v: str) -> str:
        for name in placeholders(v):
            if not name.isidentifier():
                raise ValueError(f"placeholder {{{name}}} is not a valid identifier")
        rest = _PLACEHOLDER.sub(" ", v)
        if "{" in rest or "}" in rest:
            raise ValueError("unbalanced brace in placeholder")
        for token in _NUMBER_TOKEN.findall(rest):
            core = token.rstrip(".,")
            if not (_INTEGER.fullmatch(core) and int(core) <= 10):
                raise ValueError(
                    f"digits not allowed in worked_solution outside placeholders: {token!r}"
                )
        return v


class SubjectiveItem(_Item):
    type: Literal["subjective"]
    rubric: list[str] = Field(min_length=1, max_length=10)

    @field_validator("rubric")
    @classmethod
    def _rubric_ok(cls, v: list[str]) -> list[str]:
        if any(not c.strip() for c in v):
            raise ValueError("rubric criteria must be non-empty")
        return v


QuizItem = Annotated[
    MCQItem | NumericalItem | SubjectiveItem, Field(discriminator="type")
]


class Quiz(_Strict):
    title: str = Field(min_length=1)
    items: list[QuizItem] = Field(min_length=1, max_length=20)


def parse_quiz(data: dict[str, Any] | str) -> Quiz:
    """Validate a quiz given as JSON text or an already-decoded dict."""
    if isinstance(data, str):
        data = json.loads(data)
    return Quiz.model_validate(data)


def quiz_json_schema() -> dict[str, Any]:
    """Pydantic JSON schema of a quiz, for prompts and the frontend."""
    return Quiz.model_json_schema()


@dataclass(frozen=True)
class KeyCheck:
    ok: bool
    value: float | None
    reason: str | None


def _is_real(x: object) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x)


def _fail(reason: str) -> KeyCheck:
    return KeyCheck(False, None, reason)


def check_key(result: object, item: NumericalItem) -> KeyCheck:
    """Check the two-method result a key script produced. Never raises."""
    if not isinstance(result, dict):
        return _fail("not_a_dict")
    answer, check = result.get("answer"), result.get("check")
    if not isinstance(answer, dict):
        return _fail("missing_answer")
    if not isinstance(check, dict):
        return _fail("missing_check")
    a, c = answer.get("value"), check.get("value")
    if not (_is_real(a) and _is_real(c)):
        return _fail("not_a_number")
    for part in (answer, check):
        unit = part.get("unit")
        if not isinstance(unit, str) or unit.strip() != item.unit.strip():
            return _fail("unit_mismatch")
    fa, fc = float(a), float(c)  # type: ignore[arg-type]
    allowed = item.tolerance_rel * abs(fa) if abs(fa) > _ZERO_ABS_TOL else _ZERO_ABS_TOL
    if abs(fa - fc) > allowed:
        return _fail("methods_disagree")
    return KeyCheck(True, fa, None)


def placeholders(text: str) -> list[str]:
    """Names inside ``{...}`` in order of appearance."""
    return _PLACEHOLDER.findall(text)


def _lookup(name: str, result: dict[str, Any]) -> float:
    value: object
    if name in ("answer", "check"):
        value = result[name]["value"]
    else:
        values = result.get("values")
        if isinstance(values, dict) and name in values:
            value = values[name]["value"]
        else:
            value = result[name]
    if not _is_real(value):
        raise KeyError(name)
    return float(value)  # type: ignore[arg-type]


def fill_solution(item: NumericalItem, result: dict[str, Any]) -> str:
    """Substitute sandbox numbers into the worked solution (4 significant figures).

    Raises KeyError if any placeholder has no numeric value; the caller drops the item.
    """

    def sub(m: re.Match[str]) -> str:
        try:
            return f"{_lookup(m.group(1), result):.4g}"
        except (TypeError, KeyError):
            raise KeyError(m.group(1)) from None

    return _PLACEHOLDER.sub(sub, item.worked_solution)
