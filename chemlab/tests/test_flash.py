"""Flash template tests. Independent checks: the binary two-phase closed form
x1 = (P - P2sat)/(P1sat - P2sat); Rachford-Rice re-solved as a polynomial with numpy
roots; bisection written here for bubble points; literature boiling points (CRC) and the
textbook 50/50 benzene-toluene bubble point at 1 atm (about 92 C)."""

import json
import math
import random

import numpy as np
import pytest
from chemlab._compounds import COMPOUNDS
from chemlab.flash import SPEC, run

BENZENE, TOLUENE, HEXANE, WATER, METHANE, DECANE = 14, 15, 25, 1, 19, 28


def out(r: dict, name: str) -> float:
    return r["outputs"][name]["value"]


def ps(num: int, t: float) -> float:
    c = COMPOUNDS[num - 1]
    return 10 ** (c["A"] - c["B"] / (t + c["C"]))


def bisect_bubble(nums: list[int], z: list[float], p: float) -> float:
    lo, hi = 200.0, 700.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if sum(zi * ps(n, mid) for n, zi in zip(nums, z, strict=True)) > p:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def test_benzene_toluene_textbook_bubble_point() -> None:
    r = run(series=False)
    assert r["ok"] and r["warnings"] == []
    assert out(r, "T_bubble") == pytest.approx(92.0 + 273.15, abs=0.5)
    assert out(r, "T_bubble") == pytest.approx(
        bisect_bubble([BENZENE, TOLUENE], [0.5, 0.5], 101325), abs=1e-6
    )


def test_binary_two_phase_matches_closed_form() -> None:
    t, p = 368.15, 101325.0
    p1, p2 = ps(BENZENE, t), ps(TOLUENE, t)
    x1 = (p - p2) / (p1 - p2)
    y1 = x1 * p1 / p
    v = (0.5 - x1) / (y1 - x1)
    r = run(series=False)
    assert out(r, "x1") == pytest.approx(x1, rel=1e-10)
    assert out(r, "y1") == pytest.approx(y1, rel=1e-10)
    assert out(r, "V_frac") == pytest.approx(v, rel=1e-9)
    assert out(r, "P_bubble") == pytest.approx(0.5 * (p1 + p2), rel=1e-12)
    assert out(r, "P_dew") == pytest.approx(1 / (0.5 / p1 + 0.5 / p2), rel=1e-12)


def rr_by_polynomial(z: list[float], k: list[float]) -> float:
    """Multiply out sum z_i (K_i-1) prod_{j!=i} (1 + V (K_j-1)) and take the root in (0,1)."""
    poly = np.poly1d([0.0])
    for i, (zi, ki) in enumerate(zip(z, k, strict=True)):
        term = np.poly1d([zi * (ki - 1)])
        for j, kj in enumerate(k):
            if j != i:
                term = term * np.poly1d([kj - 1, 1.0])
        poly = poly + term
    roots = [r.real for r in poly.roots if abs(r.imag) < 1e-12 and 0 < r.real < 1]
    assert len(roots) == 1
    return roots[0]


def test_ternary_matches_polynomial_rachford_rice() -> None:
    r = run({"c3": HEXANE, "n1": 0.5, "n2": 0.5, "n3": 0.3, "T": 360}, series=False)
    assert r["ok"] and "T_x" not in r["series"]
    z = [out(r, f"z{i}") for i in (1, 2, 3)]
    k = [out(r, f"K{i}") for i in (1, 2, 3)]
    assert z == pytest.approx([0.5 / 1.3, 0.5 / 1.3, 0.3 / 1.3])
    v = out(r, "V_frac")
    assert v == pytest.approx(rr_by_polynomial(z, k), rel=1e-9)
    xs = [out(r, f"x{i}") for i in (1, 2, 3)]
    ys = [out(r, f"y{i}") for i in (1, 2, 3)]
    assert sum(xs) == pytest.approx(1, abs=1e-12) and sum(ys) == pytest.approx(
        1, abs=1e-12
    )
    for zi, xi, yi in zip(z, xs, ys, strict=True):
        assert (1 - v) * xi + v * yi == pytest.approx(zi, rel=1e-12)


def test_single_phase_states() -> None:
    liq = run({"T": 340.0}, series=False)
    assert out(liq, "V_frac") == 0 and "y1" not in liq["outputs"]
    assert out(liq, "x1") == 0.5 and any("all liquid" in w for w in liq["warnings"])
    vap = run({"T": 380.0}, series=False)
    assert out(vap, "V_frac") == 1 and "x1" not in vap["outputs"]
    assert any("all vapour" in w for w in vap["warnings"])


def test_txy_end_points_are_literature_boiling_points() -> None:
    s = run()["series"]
    tx, ty = s["T_x"], s["T_y"]
    assert len(tx["x"]) == 41 and tx["y_unit"] == "K"
    assert tx["y"][0] == pytest.approx(383.8, abs=0.5)  # pure toluene (CRC 110.6 C)
    assert tx["y"][-1] == pytest.approx(353.2, abs=0.5)  # pure benzene (CRC 80.1 C)
    assert all(b < a for a, b in zip(tx["y"], tx["y"][1:], strict=False))
    assert all(yv >= xv - 1e-12 for xv, yv in zip(tx["x"], ty["x"], strict=True))
    assert ty["x"][0] == pytest.approx(0, abs=1e-12) and ty["x"][-1] == pytest.approx(1)


def test_bubble_and_dew_temperature_bracket_the_flash() -> None:
    r = run(series=False)
    assert out(r, "T_bubble") < 368.15 < out(r, "T_dew")
    # at the bubble temperature the bubble pressure equals P, by independent formula
    tb = out(r, "T_bubble")
    assert 0.5 * (ps(BENZENE, tb) + ps(TOLUENE, tb)) == pytest.approx(101325, rel=1e-9)
    td = out(r, "T_dew")
    assert 1 / (0.5 / ps(BENZENE, td) + 0.5 / ps(TOLUENE, td)) == pytest.approx(
        101325, rel=1e-9
    )


def test_warnings_extrapolation_supercritical_and_ignored_n3() -> None:
    r = run({"c1": METHANE, "c2": DECANE, "T": 300, "P": 2e6, "n3": 1})
    assert r["ok"]
    text = " ".join(r["warnings"])
    assert "methane: T outside its Antoine range" in text
    assert "above its critical temperature" in text and "n3 ignored" in text
    assert r["geometry"] == {
        "type": "flash_drum",
        "components": ["methane", "n-decane"],
    }


@pytest.mark.parametrize(
    "over,code,field",
    [
        ({"c2": BENZENE}, "same_compound", "c2"),
        ({"c3": TOLUENE}, "same_compound", "c2"),
        ({"c1": 2.5}, "not_an_integer", "c1"),
        ({"n1": 0, "n2": 0}, "empty_feed", "n1"),
        ({"c1": WATER, "T": 50}, "temperature_too_low", "T"),
        ({"c1": 41}, "out_of_range", "c1"),
        ({"P": {"value": 1, "unit": "atm"}}, "wrong_unit", "P"),
    ],
)
def test_errors(over: dict, code: str, field: str) -> None:
    r = run(over)
    assert not r["ok"]
    assert r["errors"][0]["code"] == code and r["errors"][0]["field"] == field


def test_pure_feed_of_one_compound() -> None:
    r = run({"n2": 0, "T": 353.0}, series=False)  # just below benzene's boiling point
    assert out(r, "V_frac") == 0
    assert out(r, "T_bubble") == pytest.approx(out(r, "T_dew"), rel=1e-9)


def test_random_inputs_json_safe_and_balanced() -> None:
    rng = random.Random(5)
    n_two = 0
    for _ in range(1500):
        nums = rng.sample(range(1, len(COMPOUNDS) + 1), 3)
        inp = {
            "c1": nums[0],
            "c2": nums[1],
            "c3": rng.choice([0, nums[2]]),
            "n1": rng.uniform(0, 5),
            "n2": rng.uniform(0, 5),
            "n3": rng.uniform(0, 5),
            "T": rng.uniform(SPEC["T"]["min"], 700),
            "P": 10 ** rng.uniform(3, 7),
        }
        r = run(inp, series=rng.random() < 0.05)
        json.dumps(r, allow_nan=False)
        if r["ok"] and 0 < out(r, "V_frac") < 1:
            n_two += 1
            m = 3 if inp["c3"] else 2
            v = out(r, "V_frac")
            for i in range(1, m + 1):
                z, x, y = out(r, f"z{i}"), out(r, f"x{i}"), out(r, f"y{i}")
                assert (1 - v) * x + v * y == pytest.approx(z, rel=1e-9, abs=1e-12)
            assert math.fsum(out(r, f"y{i}") for i in range(1, m + 1)) == pytest.approx(
                1, abs=1e-9
            )
    assert n_two > 50


@pytest.mark.parametrize(
    "inp",
    [
        # Psat of diethyl ether at 92 K is 1.8e-13 Pa: K = 1e-17 rounds K - 1 to -1
        {"c1": 37, "c2": 12, "T": 91.86, "P": 17269.76},
        # chloroform/1-butanol/nitrogen at 113 K: a Psat underflows to exactly 0
        {"c1": 33, "c2": 6, "c3": 37, "n1": 0, "n2": 0.47, "n3": 2.99, "T": 112.52},
    ],
)
def test_vanishing_vapour_pressure_does_not_crash(inp: dict) -> None:
    r = run(inp, series=False)
    assert r["ok"]
    json.dumps(r, allow_nan=False)
    v = out(r, "V_frac")
    if 0 < v < 1:
        ys = [v["value"] for k, v in r["outputs"].items() if k[0] == "y"]
        assert len(ys) == (3 if "c3" in inp else 2)
        assert math.fsum(ys) == pytest.approx(1, abs=1e-9)
