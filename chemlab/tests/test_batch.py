"""Batch template tests. Expected values come from closed forms or from an
independent solve_ivp integration, not from the template's own formulas."""

import json
import math
import random
import time

import numpy as np
import pytest
from chemlab.batch import SPEC, run
from chemlab.pfr import R_GAS
from scipy.integrate import solve_ivp


def params(**over: float) -> dict[str, float]:
    p = {name: s["default"] for name, s in SPEC.items()}
    p.update(over)
    return p


def ivp_ca(ca0: float, n: float, k: float, t: float) -> float:
    def rhs(_t: float, y: np.ndarray) -> list[float]:
        return [-k * max(float(y[0]), 0.0) ** n]

    sol = solve_ivp(rhs, (0.0, t), [ca0], method="LSODA", rtol=1e-8, atol=1e-12 * ca0)
    return float(sol.y[0, -1])


def test_first_order_matches_closed_form() -> None:
    r = run({"k": 0.01, "t": 200.0}, series=False)
    assert r["ok"]
    assert r["outputs"]["X"]["value"] == pytest.approx(1 - math.exp(-2.0))
    ca0 = params()["CA0"]
    assert r["outputs"]["CA"]["value"] == pytest.approx(ca0 * math.exp(-2.0), rel=1e-12)


def test_second_order_matches_closed_form() -> None:
    r = run({"n": 2, "k": 2e-5, "t": 300.0, "CA0": 500.0}, series=False)
    x = 2e-5 * 300.0 * 500.0
    assert r["outputs"]["X"]["value"] == pytest.approx(x / (1 + x), rel=1e-12)


def test_half_order_clamps_at_complete_conversion() -> None:
    inp = {"n": 0.5, "k": 0.1, "CA0": 400.0}  # t* = 20/(0.5*0.1) = 400 s
    r = run({**inp, "t": 500.0})
    assert r["outputs"]["X"]["value"] == 1.0
    assert r["outputs"]["CA"]["value"] == 0.0
    assert min(r["series"]["concentration_time"]["y"]) == 0.0
    before = run({**inp, "t": 200.0}, series=False)
    assert before["outputs"]["CA"]["value"] == pytest.approx(100.0, rel=1e-12)


def test_zero_order_clamps_at_complete_conversion() -> None:
    inp = {"n": 0, "k": 2.0, "CA0": 1000.0}
    part = run({**inp, "t": 300.0}, series=False)
    assert part["outputs"]["CA"]["value"] == pytest.approx(400.0, rel=1e-12)
    done = run({**inp, "t": 800.0}, series=False)
    assert done["outputs"]["X"]["value"] == 1.0
    assert done["outputs"]["CA"]["value"] == 0.0


def test_arrhenius_path_equals_direct_k() -> None:
    k0, ea, temp = 3.0e5, 5.0e4, 350.0
    k = k0 * math.exp(-ea / (R_GAS * temp))
    a = run({"k0": k0, "Ea": ea, "T": temp}, series=False)
    b = run({"k": k}, series=False)
    assert a["outputs"]["k_used"]["value"] == pytest.approx(k, rel=1e-12)
    assert a["outputs"]["X"]["value"] == pytest.approx(
        b["outputs"]["X"]["value"], rel=1e-12
    )
    assert a["outputs"]["T_C"]["value"] == pytest.approx(temp - 273.15)


def test_direct_k_wins_over_arrhenius() -> None:
    assert run({"k": 0.5}, series=False)["outputs"]["k_used"]["value"] == 0.5


def test_defaults_are_textbook_sensible() -> None:
    o = run(series=False)["outputs"]
    assert 0.6 < o["X"]["value"] < 0.9
    assert 0.005 < o["k_used"]["value"] < 0.02


def test_moles_reacted() -> None:
    r = run({"CA0": 1000.0, "V": 2.0}, series=False)
    assert r["outputs"]["moles_reacted"]["value"] == pytest.approx(
        1000.0 * r["outputs"]["X"]["value"] * 2.0
    )
    assert r["outputs"]["moles_reacted"]["unit"] == "mol"


@pytest.mark.parametrize("n", [0.5, 1, 1.5, 2, 3])
def test_closed_form_agrees_with_solve_ivp(n: float) -> None:
    ca0, t = 800.0, 200.0
    k = 1.5 / (t * ca0 ** (n - 1))  # Da = 1.5
    r = run({"CA0": ca0, "n": n, "k": k, "t": t}, series=False)
    assert r["outputs"]["CA"]["value"] == pytest.approx(ivp_ca(ca0, n, k, t), rel=1e-6)


@pytest.mark.parametrize("n", [0.5, 1, 2])
def test_profile_agrees_with_solve_ivp(n: float) -> None:
    ca0, t = 600.0, 250.0
    k = 1.0 / (t * ca0 ** (n - 1))
    s = run({"CA0": ca0, "n": n, "k": k, "t": t})["series"]["concentration_time"]
    for i in (0, 40, 100, len(s["x"]) - 1):
        want = ca0 if s["x"][i] == 0 else ivp_ca(ca0, n, k, s["x"][i])
        assert s["y"][i] == pytest.approx(want, rel=1e-6, abs=1e-9)


def test_target_time_closed_forms() -> None:
    k = 0.01
    first = run({"k": k, "X_target": 0.9}, series=False)
    assert first["outputs"]["t_for_target"]["value"] == pytest.approx(
        -math.log(0.1) / k
    )
    second = run({"n": 2, "k": 1e-5, "CA0": 1000.0, "X_target": 0.5}, series=False)
    assert second["outputs"]["t_for_target"]["value"] == pytest.approx(
        0.5 / (1e-5 * 1000.0 * 0.5)
    )
    zero = run({"n": 0, "k": 2.0, "CA0": 1000.0, "X_target": 0.4}, series=False)
    assert zero["outputs"]["t_for_target"]["value"] == pytest.approx(200.0)


@pytest.mark.parametrize("n", [0, 0.5, 1, 1.5, 2, 3])
@pytest.mark.parametrize("target", [0.1, 0.5, 0.9, 0.999])
def test_target_time_reproduces_target_when_fed_back(n: float, target: float) -> None:
    base = {"n": n, "k": 0.003, "CA0": 700.0}
    t = run({**base, "X_target": target}, series=False)["outputs"]["t_for_target"]
    assert math.isfinite(t["value"])
    again = run({**base, "t": t["value"]}, series=False)
    assert again["outputs"]["X"]["value"] == pytest.approx(target, rel=1e-9)


def test_target_absent_when_not_used() -> None:
    assert "t_for_target" not in run(series=False)["outputs"]


def test_target_series_extends_to_target_time() -> None:
    r = run({"t": 10.0, "X_target": 0.9})
    s = r["series"]["concentration_time"]
    assert s["x"][0] == 0.0
    assert s["x"][-1] == pytest.approx(r["outputs"]["t_for_target"]["value"])
    assert s["x"][-1] > 10.0


def test_geometry_volume_matches() -> None:
    g = run({"V": 2.0}, series=False)["geometry"]
    assert g["type"] == "batch"
    assert g["volume_m3"] == 2.0
    assert g["diameter_m"] == g["height_m"]
    assert math.pi / 4 * g["diameter_m"] ** 2 * g["height_m"] == pytest.approx(2.0)


def test_display_unit_values_are_emitted() -> None:
    o = run(series=False)["outputs"]
    assert o["X_percent"]["value"] == pytest.approx(100 * o["X"]["value"])


def test_series_shapes_and_units() -> None:
    r = run()
    s = r["series"]
    assert set(s) == {"concentration_time", "conversion_time"}
    for item in s.values():
        assert len(item["x"]) == len(item["y"]) <= 200
    assert s["concentration_time"]["x_unit"] == "s"
    assert s["concentration_time"]["x"][-1] == pytest.approx(params()["t"])
    assert s["concentration_time"]["y"][-1] == pytest.approx(
        r["outputs"]["CA"]["value"]
    )
    assert s["conversion_time"]["y"][-1] == pytest.approx(r["outputs"]["X"]["value"])


def test_negligible_reaction_is_safe() -> None:
    r = run({"k0": 1e-30, "Ea": 5e5, "T": 200.0, "X_target": 0.5})
    assert r["ok"]
    assert r["outputs"]["X"]["value"] < 1e-100
    json.dumps(r, allow_nan=False)


def test_zero_time_is_safe() -> None:
    r = run({"t": 0.0})
    assert r["outputs"]["X"]["value"] < 1e-100
    json.dumps(r, allow_nan=False)


def test_agent_path_result_fits_solve_cap() -> None:
    r = run(series=False)
    assert r["series"] == {}
    assert r["steady_states"] == [] and r["n_steady_states"] == 0
    assert len(json.dumps(r, allow_nan=False)) < 16384


@pytest.mark.parametrize(
    ("inp", "code"),
    [
        ({"Vol": 1.0}, "unknown_input"),
        ({"V": -1.0}, "out_of_range"),
        ({"n": 7}, "out_of_range"),
        ({"X_target": 1.0}, "out_of_range"),
        ({"t": "long"}, "not_a_number"),
        ({"t": True}, "not_a_number"),
        ({"t": float("nan")}, "out_of_range"),
        ({"T": {"value": 25.0, "unit": "degC"}}, "wrong_unit"),
    ],
)
def test_bad_inputs_give_structured_errors(inp: dict[str, object], code: str) -> None:
    r = run(inp)
    assert r["ok"] is False
    assert r["errors"][0]["code"] == code
    json.dumps(r, allow_nan=False)


def test_value_unit_pairs_in_canonical_unit_are_accepted() -> None:
    a = run({"t": {"value": 100.0, "unit": "s"}}, series=False)
    b = run({"t": 100.0}, series=False)
    assert a["outputs"] == b["outputs"]


def test_random_inputs_never_crash_and_stay_json_safe() -> None:
    rng = random.Random(13)
    for _ in range(300):
        inp = {
            "CA0": 10 ** rng.uniform(-2, 5),
            "V": 10 ** rng.uniform(-6, 3),
            "n": rng.choice([0, 0.5, 1, 1.0000001, 1.5, 2, 3, 4]),
            "k": rng.choice([0.0, 10 ** rng.uniform(-8, 6)]),
            "k0": 10 ** rng.uniform(-10, 30),
            "Ea": rng.uniform(0, 5e5),
            "T": rng.uniform(200, 1000),
            "t": rng.choice([0.0, 10 ** rng.uniform(-3, 8)]),
            "X_target": rng.choice([0.0, rng.uniform(0.001, 0.999999)]),
        }
        r = run(inp, series=rng.random() < 0.5)
        text = json.dumps(r, allow_nan=False)
        assert r["ok"], r["errors"]
        assert "NaN" not in text
        assert 0.0 <= r["outputs"]["X"]["value"] <= 1.0


def test_fast_enough_for_sliders() -> None:
    start = time.perf_counter()
    run()
    assert time.perf_counter() - start < 1.0
