"""PFR template tests. Expected values come from closed forms or from an
independent solve_ivp integration, not from the template's own formulas."""

import json
import math
import random
import time

import numpy as np
import pytest
from chemlab.pfr import R_GAS, SPEC, run
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
    r = run({"k": 0.01, "V": 0.2, "v0": 0.001}, series=False)
    tau = 200.0
    assert r["ok"]
    assert r["outputs"]["tau"]["value"] == pytest.approx(tau)
    assert r["outputs"]["X"]["value"] == pytest.approx(1 - math.exp(-0.01 * tau))
    ca0 = params()["CA0"]
    assert r["outputs"]["CA"]["value"] == pytest.approx(
        ca0 * math.exp(-0.01 * tau), rel=1e-12
    )


def test_second_order_matches_closed_form() -> None:
    inp = {"n": 2, "k": 2e-5, "V": 0.3, "v0": 0.001, "CA0": 500.0}
    r = run(inp, series=False)
    x = 2e-5 * 300.0 * 500.0
    assert r["outputs"]["X"]["value"] == pytest.approx(x / (1 + x), rel=1e-12)


def test_half_order_clamps_at_complete_conversion() -> None:
    # t* = CA0^0.5 / (0.5 k) = 20 / (0.5*0.1) = 400 s; tau 500 s is past it
    inp = {"n": 0.5, "k": 0.1, "CA0": 400.0, "V": 0.5, "v0": 0.001}
    r = run(inp)
    assert r["outputs"]["X"]["value"] == 1.0
    assert r["outputs"]["CA"]["value"] == 0.0
    assert min(r["series"]["concentration_profile"]["y"]) == 0.0
    before = run({**inp, "V": 0.2}, series=False)  # tau 200: CA^0.5 = 20 - 10
    assert before["outputs"]["CA"]["value"] == pytest.approx(100.0, rel=1e-12)


def test_zero_order_clamps_at_complete_conversion() -> None:
    inp = {"n": 0, "k": 2.0, "CA0": 1000.0, "v0": 0.001}
    part = run({**inp, "V": 0.3}, series=False)  # tau 300: 1000 - 600
    assert part["outputs"]["CA"]["value"] == pytest.approx(400.0, rel=1e-12)
    done = run({**inp, "V": 0.8}, series=False)
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
    r = run({"k": 0.5}, series=False)
    assert r["outputs"]["k_used"]["value"] == 0.5


def test_defaults_are_textbook_sensible() -> None:
    o = run(series=False)["outputs"]
    assert 0.6 < o["X"]["value"] < 0.9
    assert 0.005 < o["k_used"]["value"] < 0.02


@pytest.mark.parametrize("n", [0.5, 1, 1.5, 2, 3])
def test_closed_form_agrees_with_solve_ivp(n: float) -> None:
    ca0, v0, v = 800.0, 0.002, 0.4
    tau = v / v0
    k = 1.5 / (tau * ca0 ** (n - 1))  # Da = 1.5
    r = run({"CA0": ca0, "v0": v0, "V": v, "n": n, "k": k}, series=False)
    assert r["outputs"]["CA"]["value"] == pytest.approx(
        ivp_ca(ca0, n, k, tau), rel=1e-6
    )


@pytest.mark.parametrize("n", [0.5, 1, 2])
def test_profile_agrees_with_solve_ivp(n: float) -> None:
    ca0, tau = 600.0, 250.0
    k = 1.0 / (tau * ca0 ** (n - 1))
    r = run({"CA0": ca0, "v0": 0.001, "V": 0.25, "n": n, "k": k})
    s = r["series"]["concentration_profile"]
    for i in (0, 40, 100, len(s["x"]) - 1):
        t = tau * s["x"][i] / r["geometry"]["length_m"]
        want = ca0 if t == 0 else ivp_ca(ca0, n, k, t)
        assert s["y"][i] == pytest.approx(want, rel=1e-6, abs=1e-9)


def test_length_from_volume_and_diameter() -> None:
    r = run({"V": 0.5, "D": 0.2}, series=False)
    length = 4 * 0.5 / (math.pi * 0.2**2)
    assert r["outputs"]["length_m"]["value"] == pytest.approx(length)
    g = r["geometry"]
    assert g["type"] == "pfr"
    assert g["length_m"] == pytest.approx(length)
    assert g["diameter_m"] == 0.2
    assert g["volume_m3"] == 0.5


def test_display_unit_values_are_emitted() -> None:
    o = run(series=False)["outputs"]
    assert o["X_percent"]["value"] == pytest.approx(100 * o["X"]["value"])


def test_series_shapes_and_units() -> None:
    r = run()
    s = r["series"]
    assert set(s) == {"concentration_profile", "conversion_profile", "levenspiel"}
    for item in s.values():
        assert len(item["x"]) == len(item["y"]) <= 200
    assert s["concentration_profile"]["x_unit"] == "m"
    assert s["concentration_profile"]["x"][-1] == pytest.approx(
        r["outputs"]["length_m"]["value"]
    )
    assert s["concentration_profile"]["y"][-1] == pytest.approx(
        r["outputs"]["CA"]["value"]
    )
    assert s["levenspiel"]["y_unit"] == "m^3 s/mol"
    lev = s["levenspiel"]
    assert lev["x"][0] == 0.0 and lev["x"][-1] <= 0.95
    p = params()
    k = r["outputs"]["k_used"]["value"]
    assert lev["y"][0] == pytest.approx(1 / (k * p["CA0"] ** p["n"]))


def test_negligible_reaction_is_safe() -> None:
    r = run({"k0": 1e-30, "Ea": 5e5, "T": 200.0})
    assert r["ok"]
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
        ({"V": "big"}, "not_a_number"),
        ({"V": True}, "not_a_number"),
        ({"V": float("nan")}, "out_of_range"),
        ({"T": {"value": 25.0, "unit": "degC"}}, "wrong_unit"),
    ],
)
def test_bad_inputs_give_structured_errors(inp: dict[str, object], code: str) -> None:
    r = run(inp)
    assert r["ok"] is False
    assert r["errors"][0]["code"] == code
    json.dumps(r, allow_nan=False)


def test_value_unit_pairs_in_canonical_unit_are_accepted() -> None:
    a = run({"T": {"value": 360.0, "unit": "K"}}, series=False)
    b = run({"T": 360.0}, series=False)
    assert a["outputs"] == b["outputs"]


def test_random_inputs_never_crash_and_stay_json_safe() -> None:
    rng = random.Random(11)
    for _ in range(300):
        inp = {
            "CA0": 10 ** rng.uniform(-2, 5),
            "v0": 10 ** rng.uniform(-6, 2),
            "V": 10 ** rng.uniform(-6, 3),
            "D": 10 ** rng.uniform(-3, 1),
            "n": rng.choice([0, 0.5, 1, 1.0000001, 1.5, 2, 3, 4]),
            "k": rng.choice([0.0, 10 ** rng.uniform(-8, 6)]),
            "k0": 10 ** rng.uniform(-10, 30),
            "Ea": rng.uniform(0, 5e5),
            "T": rng.uniform(200, 1000),
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
