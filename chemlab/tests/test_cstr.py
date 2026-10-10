"""CSTR template tests. Expected values come from closed forms or from an
independent temperature scan, not from the template's own X-scan."""

import itertools
import json
import math
import random
import time

import numpy as np
import pytest
from chemlab.cstr import R_GAS, SPEC, run
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

ADIABATIC = {}  # the defaults: first order, adiabatic, three steady states


def k_at(p: dict[str, float], T: float) -> float:
    return p["k0"] * math.exp(-p["Ea"] / (R_GAS * T))


def params(**over: float) -> dict[str, float]:
    p = {name: s["default"] for name, s in SPEC.items()}
    p.update(over)
    return p


def assert_balances(p: dict[str, float], state: dict[str, float]) -> None:
    """Both balances in forms that do not cancel: CA0*X against tau*k*CA^n, and the
    energy balance to 1e-6 relative or 1 nK of temperature, whichever is looser."""
    T, X, ca = state["T"], state["X"], state["CA"]
    tau = p["V"] / p["v0"]
    reacted = p["CA0"] * X
    if p["n"] == 0 and X == 1.0:  # zero order ran out of A: needs k*tau >= CA0
        assert k_at(p, T) * tau >= p["CA0"]
    else:
        assert math.isclose(reacted, tau * k_at(p, T) * ca ** p["n"], rel_tol=1e-6)
    assert math.isclose(state["rate"], reacted / tau, rel_tol=1e-9)
    if p["isothermal"] < 0.5:
        gen = -p["dHr"] * p["v0"] * p["CA0"] * X
        rem = p["rho_cp"] * p["v0"] * (T - p["T0"]) + p["UA"] * (T - p["Ta"])
        slope = p["rho_cp"] * p["v0"] + p["UA"]
        assert abs(gen - rem) <= 1e-6 * max(abs(gen), abs(rem)) + slope * 1e-9


@pytest.mark.parametrize("T0", [300.0, 320.0, 350.0])
def test_isothermal_first_order_matches_closed_form(T0: float) -> None:
    p = params(isothermal=1, T0=T0)
    r = run({"isothermal": 1, "T0": T0}, series=False)
    da = k_at(p, T0) * p["V"] / p["v0"]
    assert r["ok"]
    assert r["outputs"]["X"]["value"] == pytest.approx(da / (1 + da), rel=1e-9)
    assert r["outputs"]["T"]["value"] == T0
    assert r["n_steady_states"] == 1


def test_isothermal_second_order_matches_quadratic() -> None:
    inp = {"isothermal": 1, "n": 2, "k0": 1e6, "CA0": 500.0}
    p = params(**inp)
    da = k_at(p, p["T0"]) * p["V"] / p["v0"] * p["CA0"]
    expected = ((2 * da + 1) - math.sqrt(4 * da + 1)) / (2 * da)
    r = run(inp, series=False)
    assert r["outputs"]["X"]["value"] == pytest.approx(expected, rel=1e-9)


def test_isothermal_zero_order_caps_at_full_conversion() -> None:
    p = params(n=0, k0=1e12, isothermal=1)
    r = run({"n": 0, "k0": 1e12, "isothermal": 1}, series=False)
    expected = min(k_at(p, p["T0"]) * p["V"] / p["v0"] / p["CA0"], 1.0)
    assert r["outputs"]["X"]["value"] == pytest.approx(expected, rel=1e-9)


def independent_adiabatic_states(p: dict[str, float]) -> list[float]:
    """First order only: X(T) = Da/(1+Da); roots of G(T) - R(T) by a T scan."""
    tau = p["V"] / p["v0"]

    def g_minus_r(T: float) -> float:
        da = k_at(p, T) * tau
        gen = -p["dHr"] * p["v0"] * p["CA0"] * da / (1 + da)
        return gen - p["rho_cp"] * p["v0"] * (T - p["T0"]) - p["UA"] * (T - p["Ta"])

    Ts = np.linspace(p["T0"] - 50, p["T0"] + 400, 20001)
    f = [g_minus_r(T) for T in Ts]
    return [
        brentq(g_minus_r, Ts[i], Ts[i + 1])
        for i in range(len(Ts) - 1)
        if f[i] * f[i + 1] < 0
    ]


def test_adiabatic_three_steady_states_match_independent_scan() -> None:
    r = run(ADIABATIC, series=False)
    p = params()
    expected = independent_adiabatic_states(p)
    assert len(expected) == 3
    assert r["n_steady_states"] == 3
    for state, T in zip(r["steady_states"], expected, strict=True):
        assert state["T"] == pytest.approx(T, rel=1e-6)
        assert_balances(p, state)
    assert [s["stable"] for s in r["steady_states"]] == [True, False, True]
    # outputs report the stable state a start-up from the feed reaches
    assert r["outputs"]["T"]["value"] == r["steady_states"][0]["T"]
    assert any("3 steady states" in w for w in r["warnings"])


def test_hotter_feed_leaves_only_the_ignited_state() -> None:
    p = params(T0=340.0)
    r = run({"T0": 340.0}, series=False)
    expected = independent_adiabatic_states(p)
    assert r["n_steady_states"] == len(expected) == 1
    assert r["steady_states"][0]["T"] == pytest.approx(expected[0], rel=1e-6)
    assert r["outputs"]["X"]["value"] > 0.9


@pytest.mark.parametrize(
    "inp",
    [
        {"UA": 2e4, "Ta": 290.0},  # cooled
        {"UA": 5e3, "Ta": 310.0, "n": 2, "k0": 1e7},  # second order
        {"n": 0.5, "k0": 1e9},  # fractional order
        {"dHr": 5e4},  # endothermic
        {"n": 0, "k0": 1e13, "Ea": 9e4},  # zero order
    ],
)
def test_every_state_satisfies_both_balances(inp: dict[str, float]) -> None:
    r = run(inp, series=False)
    assert r["ok"], r["errors"]
    assert r["n_steady_states"] >= 1
    for state in r["steady_states"]:
        assert_balances(params(**inp), state)


def test_zero_order_full_conversion_is_a_steady_state() -> None:
    # cold state plus an ignited state that uses up all of A
    inp = {
        "n": 0,
        "CA0": 6.62e4,
        "v0": 1.14e-6,
        "V": 0.024,
        "k0": 3.07e7,
        "Ea": 1.96e5,
        "dHr": -4.45e5,
        "T0": 455.0,
    }
    r = run(inp, series=False)
    states = r["steady_states"]
    assert [s["X"] for s in states][-1] == 1.0
    assert [s["stable"] for s in states] == [True, False, True]
    for state in states:
        assert_balances(params(**inp), state)


def test_oscillating_state_is_not_called_stable() -> None:
    # The only steady state passes the slope test (dR/dT > dG/dT) but the transient
    # Jacobian has trace > 0: the reactor runs a limit cycle (311-423 K by solve_ivp)
    # instead of sitting at ~330 K.
    inp = {
        "CA0": 5000.0,
        "v0": 3.4e-4,
        "V": 0.32,
        "k0": 3.4e13,
        "Ea": 1.0e5,
        "dHr": -1.9e5,
        "UA": 9500.0,
        "Ta": 303.6,
        "T0": 318.2,
    }
    r = run(inp, series=False)
    assert r["n_steady_states"] == 1
    assert r["steady_states"][0]["stable"] is False
    assert any("oscillat" in w for w in r["warnings"])
    p = params(**inp)
    T = r["steady_states"][0]["T"]
    sol = solve_ivp(
        lambda _, y: transient(p, y),
        (0.0, 40.0 * p["V"] / p["v0"]),
        [r["steady_states"][0]["CA"] * 1.001, T],
        rtol=1e-10,
        atol=1e-8,
        method="LSODA",
    )
    late = sol.y[1][sol.t > 30.0 * p["V"] / p["v0"]]
    assert late.max() - late.min() > 50.0  # sustained swing, not a decay to T


def test_stable_labels_match_jacobian_eigenvalues() -> None:
    for inp in (ADIABATIC, {"UA": 2e4, "Ta": 290.0}, {"dHr": 5e4}):
        p = params(**inp)
        for state in run(inp, series=False)["steady_states"]:
            eig = np.linalg.eigvals(jacobian(p, state["CA"], state["T"]))
            assert state["stable"] == bool(eig.real.max() < 0.0)


def transient(p: dict[str, float], y: list[float]) -> list[float]:
    CA, T = y
    k = p["k0"] * math.exp(-p["Ea"] / (R_GAS * T))
    r = k * max(CA, 0.0) ** p["n"]
    tau = p["V"] / p["v0"]
    heat = (
        p["rho_cp"] * p["v0"] * (p["T0"] - T)
        - p["UA"] * (T - p["Ta"])
        - p["dHr"] * p["V"] * r
    )
    return [(p["CA0"] - CA) / tau - r, heat / (p["rho_cp"] * p["V"])]


def jacobian(p: dict[str, float], CA: float, T: float) -> np.ndarray:
    # central differences of the transient model, independent of the template
    y0 = np.array([CA, T])
    J = np.zeros((2, 2))
    for j in range(2):
        h = 1e-6 * max(abs(y0[j]), 1.0)
        up, dn = y0.copy(), y0.copy()
        up[j] += h
        dn[j] -= h
        J[:, j] = (
            np.array(transient(p, list(up))) - np.array(transient(p, list(dn)))
        ) / (2 * h)
    return J


def test_endothermic_states_are_stable() -> None:
    r = run({"dHr": 5e4}, series=False)
    assert all(s["stable"] for s in r["steady_states"])


def test_zero_heat_of_reaction_is_safe() -> None:
    p = params(dHr=0.0, UA=1e4, Ta=280.0)
    r = run({"dHr": 0.0, "UA": 1e4, "Ta": 280.0}, series=False)
    a = p["rho_cp"] * p["v0"]
    expected_T = (a * p["T0"] + p["UA"] * p["Ta"]) / (a + p["UA"])
    assert r["n_steady_states"] == 1
    assert r["outputs"]["T"]["value"] == pytest.approx(expected_T, rel=1e-9)


def test_zero_activation_energy_uses_energy_balance_temperature() -> None:
    r = run({"Ea": 0.0, "k0": 0.01}, series=False)
    p = params(Ea=0.0, k0=0.01)
    assert r["n_steady_states"] == 1
    assert_balances(p, r["steady_states"][0])


def test_display_unit_values_are_emitted() -> None:
    o = run(series=False)["outputs"]
    assert o["X_percent"]["value"] == pytest.approx(100 * o["X"]["value"])
    assert o["T_C"]["value"] == pytest.approx(o["T"]["value"] - 273.15)


def test_series_shapes_and_units() -> None:
    s = run()["series"]
    assert set(s) == {"s_curve", "levenspiel", "heat_generated", "heat_removed"}
    for item in s.values():
        assert len(item["x"]) == len(item["y"]) <= 200
    assert s["s_curve"]["x_unit"] == "s"
    iso = run({"isothermal": 1})["series"]
    assert set(iso) == {"s_curve", "levenspiel"}


def test_agent_path_result_fits_solve_cap() -> None:
    r = run(series=False)
    assert r["series"] == {}
    assert len(json.dumps(r, allow_nan=False)) < 16384


def test_geometry_volume_matches() -> None:
    g = run({"V": 2.0}, series=False)["geometry"]
    assert math.pi / 4 * g["diameter_m"] ** 2 * g["height_m"] == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("inp", "code"),
    [
        ({"Vol": 1.0}, "unknown_input"),
        ({"V": -1.0}, "out_of_range"),
        ({"n": 7}, "out_of_range"),
        ({"V": "big"}, "not_a_number"),
        ({"V": True}, "not_a_number"),
        ({"V": float("nan")}, "out_of_range"),
        ({"T0": {"value": 25.0, "unit": "degC"}}, "wrong_unit"),
    ],
)
def test_bad_inputs_give_structured_errors(inp: dict[str, object], code: str) -> None:
    r = run(inp)
    assert r["ok"] is False
    assert r["errors"][0]["code"] == code
    json.dumps(r, allow_nan=False)


def test_value_unit_pairs_in_canonical_unit_are_accepted() -> None:
    a = run({"T0": {"value": 310.0, "unit": "K"}}, series=False)
    b = run({"T0": 310.0}, series=False)
    assert a["outputs"] == b["outputs"]


def test_random_inputs_never_crash_and_stay_json_safe() -> None:
    rng = random.Random(7)
    for _ in range(300):
        inp = {
            "CA0": 10 ** rng.uniform(0, 4),
            "v0": 10 ** rng.uniform(-4, 0),
            "V": 10 ** rng.uniform(-2, 2),
            "n": rng.choice([0, 0.5, 1, 1.5, 2]),
            "k0": 10 ** rng.uniform(0, 15),
            "Ea": rng.uniform(0, 1.5e5),
            "dHr": rng.uniform(-3e5, 1e5),
            "UA": rng.choice([0, 10 ** rng.uniform(1, 5)]),
            "Ta": rng.uniform(250, 400),
            "T0": rng.uniform(250, 400),
            "isothermal": rng.choice([0, 1]),
        }
        r = run(inp)
        text = json.dumps(r, allow_nan=False)
        assert "NaN" not in text
        if r["ok"]:
            for state in r["steady_states"]:
                assert_balances(params(**inp), state)


def test_fast_enough_for_sliders() -> None:
    start = time.perf_counter()
    run()
    assert time.perf_counter() - start < 1.0


def _branches(r: dict) -> tuple[list[dict], np.ndarray, np.ndarray]:
    sc = r["series"]["s_curve"]
    return (
        sc["branches"],
        np.array(sc["x"], dtype=float),
        np.array(sc["y"], dtype=float),
    )


def test_s_curve_branches_split_the_fold() -> None:
    # default inputs have 3 steady states: the S-curve folds back twice
    r = run({}, series=True)
    branches, tau, X = _branches(r)
    assert [b["stable"] for b in branches] == [True, False, True]
    # contiguous, in X order, covering every point
    assert branches[0]["start"] == 0 and branches[-1]["stop"] == len(X)
    for a, b in itertools.pairwise(branches):
        assert a["stop"] == b["start"]
    # residence time is monotonic inside each branch, so a renderer that sorts by x
    # (or draws each branch as its own line) cannot zig-zag
    for b in branches:
        d = np.diff(tau[b["start"] : b["stop"]])
        assert np.all(d > 0) or np.all(d < 0)


def test_s_curve_branch_labels_match_independent_eigenvalues() -> None:
    p = params()
    r = run({}, series=True)
    branches, tau, X = _branches(r)
    for b in branches:
        for i in range(b["start"], b["stop"], 7):
            q = dict(p, V=tau[i] * p["v0"])  # the curve varies V at fixed v0
            T = (
                -q["dHr"] * q["v0"] * q["CA0"] * X[i]
                + q["rho_cp"] * q["v0"] * q["T0"]
                + q["UA"] * q["Ta"]
            ) / (q["rho_cp"] * q["v0"] + q["UA"])
            eig = np.linalg.eigvals(jacobian(q, q["CA0"] * (1 - X[i]), T))
            if abs(eig.real.max()) > 1e-9:  # skip points on a fold
                assert b["stable"] == bool(eig.real.max() < 0.0)


def test_s_curve_isothermal_is_one_stable_branch() -> None:
    r = run({"isothermal": 1.0}, series=True)
    branches, _, X = _branches(r)
    assert branches == [{"stable": True, "start": 0, "stop": len(X)}]


def test_s_curve_operating_point_sits_on_a_branch_with_its_label() -> None:
    # every reported steady state lies on the S-curve at the reactor's tau, on a
    # branch with the same stability label
    r = run({}, series=True)
    branches, tau, X = _branches(r)
    tau_op = r["inputs"]["V"]["value"] / r["inputs"]["v0"]["value"]
    for st in r["steady_states"]:
        i = int(np.argmin(np.abs(X - st["X"])))
        b = next(b for b in branches if b["start"] <= i < b["stop"])
        assert b["stable"] == st["stable"]
        assert math.isclose(tau[i], tau_op, rel_tol=0.2)


def test_s_curve_splits_a_fold_between_two_unstable_branches() -> None:
    # Cooled reactor where an oscillating state (trace > 0) sits next to the
    # saddle branch: the label is "unstable" on both sides of the fold, so the split
    # must also happen where tau turns back.
    inp = {
        "CA0": 1289.0,
        "v0": 0.02779,
        "V": 2.577,
        "Ea": 84730.0,
        "dHr": -209900.0,
        "rho_cp": 426500.0,
        "UA": 11610.0,
        "Ta": 306.0,
        "T0": 286.4,
        "k0": 2.399e10,
    }
    r = run(inp, series=True)
    branches, tau, _ = _branches(r)
    assert any(
        not a["stable"] and not b["stable"] for a, b in itertools.pairwise(branches)
    )
    for b in branches:
        d = np.diff(tau[b["start"] : b["stop"]])
        assert np.all(d > 0) or np.all(d < 0)
