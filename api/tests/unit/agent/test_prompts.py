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


def test_method_cards_follow_the_topic_not_the_question() -> None:
    from app.agent.prompts import method_cards

    assert "rayleigh_residue" in (method_cards("Simple batch distillation of 100 mol ...") or "")
    assert "chemlab.mccabe" in (method_cards("How many theoretical plates are needed?") or "")
    assert "rachford_rice" in (method_cards("An isothermal flash drum receives ...") or "")
    assert method_cards("Find the Reynolds number in a 50 mm pipe") is None


def test_z_table_card_extrapolates_the_integrands_to_zero_pressure() -> None:
    # (dZ/dT)/P and (Z-1)/P tend to finite limits at P = 0; setting them to 0 cost ~7 %
    # of H^R on a Z-table question, and solver and re-solve agreed on it (wrong at high)
    card = prompts.method_cards("residual enthalpy from a table of compressibility factors") or ""
    assert "do NOT vanish at P = 0" in card and "never set them to 0" in card
    assert "dZ/dT = 0 there" not in card


def test_a_named_method_is_checked_by_itself_not_another_correlation() -> None:
    # 27 Oct: "by the Lee/Kesler correlations" checked with Pitzer virial at Pr = 2.4 (4 % off,
    # 0.5 % needed): every named-method question fell to the re-solve, which then had to luck in
    assert "different model or\n   correlation than the one the question names" in prompts.SOLVER
    assert "names a method or correlation, use that one" in prompts.CROSS_CHECK
    card = prompts.method_cards("by the Lee/Kesler correlations") or ""
    assert "that same one by a second route" in card and "never another correlation" in card
