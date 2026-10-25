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
    for name in TOOL_NAMES:  # every tool the solver is offered (web_search is not wired)
        assert (name in s) == (name != "web_search"), name


def test_explain_only_uses_result_numbers() -> None:
    e = prompts.EXPLAIN
    assert "ONLY numbers" in e and "4 significant figures" in e and "answer_md" in e
    assert "{bad}" in prompts.REGENERATE
    assert "{reason}" in prompts.REPAIR


def test_concept_states_no_numbers() -> None:
    assert "Do not state any computed numerical values" in prompts.CONCEPT


def test_classify_defaults_to_calc() -> None:
    assert 'When unsure, reply "calc"' in prompts.CLASSIFY


def test_solver_guards_correlation_units() -> None:
    s = prompts.SOLVER
    assert "units they are written in" in s and "physically sensible size" in s


def test_explain_lists_assumed_values_and_verdict_words() -> None:
    e = prompts.EXPLAIN
    assert "that the question did not state" in e and "question's own word" in e
    assert "conversion factor" in prompts.SOLVER and '"assumptions"' in prompts.SOLVER
    assert "placeholders" in prompts.REGENERATE
    assert "SAME quantity" in prompts.SOLVER and "limiting case" in prompts.SOLVER
    prompts.REGENERATE.format(bad="1000")


def test_classify_routes_derivations_and_lookups() -> None:
    c = prompts.CLASSIFY
    assert "obtain an expression" in c and "unless the question gives numbers" in c
    assert "is study and" in c and "NOT live" in c


def test_concept_has_derivation_structure() -> None:
    k = prompts.CONCEPT
    assert "final result as a display equation" in k and "Never invent numbers" in k
    assert "define every symbol" in k
