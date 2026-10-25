from typing import Any

from app.agent.verify import asked_parts, missing_parts, sanity, verify


def result(**values: tuple[float, str]) -> dict[str, Any]:
    return {
        "answer": {"value": 2.0, "unit": "-"},
        "check": {"value": 2.0, "unit": "-", "method": "numeric"},
        "values": {k: {"value": v, "unit": u} for k, (v, u) in values.items()},
    }


def test_102_stages_with_feed_stage_0_fails() -> None:
    r = result(n_stages=(102, "-"), feed_stage=(0, "-"))
    assert sanity(r) is not None
    v = verify(r)
    assert not v.ok and not v.disagree and "stage" in (v.reason or "")


def test_fraction_above_one_fails_and_percent_is_0_to_100() -> None:
    assert sanity(result(X=(1.2, "-"))) is not None
    assert sanity(result(conversion=(0.8, "-"))) is None
    assert sanity(result(conversion_percent=(80.0, "%"))) is None
    assert sanity(result(conversion_percent=(120.0, "%"))) is not None


def test_stage_range_and_feed_beyond_the_column_fail() -> None:
    assert sanity(result(n_stages=(13.4, "-"))) is None  # Gilliland gives fractional stages
    assert sanity(result(n_stages=(151, "-"))) is not None
    assert sanity(result(N_min=(7.3, "-"))) is None  # Fenske is not whole
    assert sanity(result(n_stages=(10, "-"), feed_stage=(11, "-"))) is not None
    assert sanity(result(n_stages=(10, "-"), feed_stage=(5, "-"))) is None


def test_absolute_units_and_flows() -> None:
    assert sanity(result(T_out=(-5.0, "K"))) is not None
    assert sanity(result(P_out=(0.0, "kPa"))) is not None
    assert sanity(result(P_drop=(-3.0, "kPa"))) is None
    assert sanity(result(F_flow=(-1.0, "mol/s"))) is not None
    assert sanity(result(x_m=(5.0, "m"))) is None  # a position, not a fraction


def test_non_finite_fails_and_a_change_question_may_be_negative() -> None:
    r = result()
    r["values"]["h"] = {"value": float("inf"), "unit": "m"}
    assert sanity(r) is not None
    neg = {
        "answer": {"value": -20.0, "unit": "K"},
        "check": {"value": -20.0, "unit": "K"},
    }
    assert sanity(neg) is not None
    assert sanity(neg, "Find the temperature change") is None


def test_asked_parts_counts_markers_clauses_and_also() -> None:
    assert asked_parts("(a) find h and (b) heat loss per metre") == 2
    assert asked_parts("Compute NPSHa and state whether cavitation is expected") == 2
    assert asked_parts("Find the pump head for 0.02 m3/s") == 1
    assert asked_parts("Find X. Also give Y.") == 2
    assert asked_parts("Answer only part (b): what is Re?") == 1


def test_missing_parts_needs_listed_known_names() -> None:
    q = "(a) find h and (b) heat loss per metre"
    assert missing_parts(result(q=(1.0, "W/m")), "Find h") is None
    assert missing_parts(result(q=(1.0, "W/m")), q) is not None
    one = {**result(q=(1.0, "W/m")), "parts": ["answer"]}
    assert "result has 1" in (missing_parts(one, q) or "")
    ghost = {**one, "parts": ["answer", "nope"]}
    assert missing_parts(ghost, q) is not None
    assert missing_parts({**one, "parts": ["answer", "q"]}, q) is None


def test_signed_energy_flows_and_conversion_factors_pass() -> None:
    assert sanity(result(heat_flow=(-50.0, "kW"))) is None  # heat removed
    assert sanity(result(conversion_factor=(1000.0, "-"))) is None
    assert sanity(result(kPa_per_MPa=(1000.0, "-"))) is None
    assert sanity(result(conversion=(1.2, "-"))) is not None


def test_stage_count_question_rejects_a_fraction_of_a_stage() -> None:
    from app.agent.verify import sanity

    q = "Use the Kremser equation to find the number of ideal stages required."
    bad = {"answer": {"value": 0.0173, "unit": "-"}, "check": {"value": 0.0173, "unit": "-"}}
    good = {"answer": {"value": 8.05, "unit": "-"}, "check": {"value": 8.05, "unit": "-"}}
    assert sanity(bad, q) is not None and "stages" in sanity(bad, q)  # type: ignore[operator]
    assert sanity(good, q) is None
    # a two-part question's main answer may be something else (e.g. a reflux ratio)
    two = "Find the number of stages and also report the minimum reflux ratio."
    assert sanity({**bad}, two) is None


def test_a_stream_flow_named_by_symbol_cannot_be_negative() -> None:
    from app.agent.verify import sanity

    r = {"answer": {"value": 135.98, "unit": "kmol/h"}, "check": {"value": 135.98, "unit": "kmol/h"},
         "values": {"L_bar": {"value": -40.0, "unit": "kmol/h"}}}
    assert sanity(r, "Find the stripping-section vapour flow.") is not None


def test_reaction_rates_may_be_negative_but_flows_may_not() -> None:
    assert sanity(result(r_A=(-0.5, "mol/s"))) is None
    assert sanity(result(rate_A=(-0.5, "mol/s"))) is None
    assert sanity(result(L=(-2.0, "kmol/h"))) is not None
