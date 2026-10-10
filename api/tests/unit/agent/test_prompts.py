"""Pin the rules the prompts must keep (they mirror the sandbox and the guardrail)."""

from app.agent import prompts
from app.agent.tools import TOOL_NAMES


def test_solver_keeps_the_sandbox_rules() -> None:
    s = prompts.SOLVER
    for rule in (
        "TWO",
        "float(",
        "NaN",
        "16 KB",
        "no arrays",
        "No variables survive",
        "plt.show()",
        "600 characters",
        '"answer"',
        '"check"',
        '"values"',
        "quoted data",
    ):
        assert rule in s, rule
    for name in TOOL_NAMES:
        assert name in s


def test_explain_only_uses_result_numbers() -> None:
    e = prompts.EXPLAIN
    assert "ONLY numbers" in e and "4 significant figures" in e and "answer_md" in e
    assert "{bad}" in prompts.REGENERATE
    assert "{reason}" in prompts.REPAIR


def test_concept_states_no_numbers() -> None:
    assert "Do not state any computed numerical values" in prompts.CONCEPT


def test_classify_defaults_to_calc() -> None:
    assert 'When unsure, reply "calc"' in prompts.CLASSIFY
