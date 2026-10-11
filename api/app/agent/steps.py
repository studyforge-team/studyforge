"""Step and result shapes of the solve API (master plan §3.5, as typed by the web
client in web/src/api/types.ts). Change only together with the contract."""

from typing import Any, Literal

from pydantic import BaseModel, Field

RUN_TIMEOUT_S: Literal[10] = 10


class RunPython(BaseModel):
    type: Literal["run_python"] = "run_python"
    code: str
    timeout_s: Literal[10] = RUN_TIMEOUT_S


class NeedConfirm(BaseModel):
    type: Literal["need_confirm"] = "need_confirm"
    extracted_text: str


class Source(BaseModel):
    title: str
    url: str | None = None


class Final(BaseModel):
    type: Literal["final"] = "final"
    answer_md: str
    numbers: dict[str, float] = Field(default_factory=dict)
    figures: list[str] = Field(default_factory=list)
    diagram_mermaid: str | None = None
    sources: list[Source] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


Step = RunPython | NeedConfirm | Final


class ResultBody(BaseModel):
    """What the browser worker posts after running a run_python step."""

    stdout: str = ""
    result: Any = None
    figures: list[str] = Field(default_factory=list)  # bare base64 PNG
    error: str | None = None
    ms: float = 0


def step_json(step: Step) -> dict[str, Any]:
    """The wire form: optional fields the client does not expect are left out."""
    return step.model_dump(exclude_none=True)
