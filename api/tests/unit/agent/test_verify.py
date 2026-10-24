from typing import Any

from app.agent.verify import sanity, verify


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


def test_non_whole_stages_and_feed_beyond_the_column_fail() -> None:
    assert sanity(result(n_stages=(12.5, "-"))) is not None
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
