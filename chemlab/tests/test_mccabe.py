"""McCabe-Thiele tests. Expected values come from hand calculations, the Fenske
equation and an independent quadratic for the q-line/equilibrium intersection."""

import json
import math
import random
import time
from typing import Any

import pytest
from chemlab.mccabe import R_GAS, SPEC, run

ALPHA = 2.5


def eq(x: float, a: float = ALPHA) -> float:
    return a * x / (1 + (a - 1) * x)


def out(r: dict[str, Any], name: str) -> float:
    return float(r["outputs"][name]["value"])


def test_rmin_saturated_liquid_hand_calc() -> None:
    r = run({"q": 1}, series=False)
    assert r["ok"]
    assert out(r, "x_star") == pytest.approx(0.5, abs=1e-12)
    assert out(r, "y_star") == pytest.approx(1.25 / 1.75, abs=1e-12)
    assert out(r, "Rmin") == pytest.approx(1.1, abs=1e-12)


def test_rmin_saturated_vapour_hand_calc() -> None:
    r = run({"q": 0}, series=False)
    assert out(r, "y_star") == pytest.approx(0.5, abs=1e-12)
    assert out(r, "x_star") == pytest.approx(0.5 / 1.75, abs=1e-12)
    assert out(r, "Rmin") == pytest.approx(2.1, abs=1e-12)


@pytest.mark.parametrize("q", [-1.5, -0.3, 0.5, 0.9, 1.1, 1.5, 2.5])
def test_rmin_general_q_matches_quadratic(q: float) -> None:
    # alpha x = (m x + c)(1 + (alpha-1) x)  ->  A x^2 + B x + C = 0
    zF, a = 0.5, ALPHA
    m, c = q / (q - 1), -zF / (q - 1)
    A, B, C = m * (a - 1), m + c * (a - 1) - a, c
    disc = math.sqrt(B * B - 4 * A * C)
    roots = [(-B + disc) / (2 * A), (-B - disc) / (2 * A)]
    x = next(t for t in roots if 0 < t < 1 and 0 < m * t + c < 1)
    y = m * x + c
    r = run({"q": q}, series=False)
    assert r["ok"]
    assert out(r, "Rmin") == pytest.approx((0.95 - y) / (y - x), rel=1e-9)


def test_balances() -> None:
    r = run({"F": 250, "zF": 0.4, "xD": 0.97, "xB": 0.03}, series=False)
    D, B = out(r, "D"), out(r, "B")
    assert D + B == pytest.approx(250)
    assert D * 0.97 + B * 0.03 == pytest.approx(250 * 0.4)
    assert D == pytest.approx(250 * 0.37 / 0.94)


def test_fenske_at_very_high_reflux() -> None:
    rmin = out(run(series=False), "Rmin")
    nmin = math.log(0.95 / 0.05 * 0.95 / 0.05) / math.log(ALPHA)
    assert nmin == pytest.approx(6.43, abs=0.01)
    r = run({"R": 1000 * rmin}, series=False)
    assert r["ok"]
    assert out(r, "N_theoretical") == math.ceil(nmin) == 7
    assert out(r, "N_fractional") == pytest.approx(nmin, abs=0.15)


def test_stages_increase_toward_minimum_reflux() -> None:
    counts = []
    for f in [5.0, 2.0, 1.5, 1.3, 1.1, 1.03]:
        r = run({"R_factor": f}, series=False)
        counts.append(out(r, "N_theoretical") if r["ok"] else 201)
    assert counts == sorted(counts)
    assert counts[0] < counts[-1]


def test_reflux_below_minimum_is_structured_error() -> None:
    rmin = out(run(series=False), "Rmin")
    for R in (0.5 * rmin, rmin):
        r = run({"R": R}, series=False)
        assert not r["ok"]
        assert r["errors"][0]["code"] == "reflux_below_minimum"
        assert r["errors"][0]["field"] == "R"
        json.dumps(r, allow_nan=False)


def test_near_pinch_never_crashes() -> None:
    r = run({"R_factor": 1.0001})
    json.dumps(r, allow_nan=False)
    if r["ok"]:
        assert out(r, "N_theoretical") > 30
    else:
        assert r["errors"][0]["code"] == "too_many_stages"


def test_too_many_stages_error() -> None:
    r = run({"alpha": 1.02, "R_factor": 5.0}, series=False)
    assert not r["ok"]
    assert r["errors"][0]["code"] == "too_many_stages"


@pytest.mark.parametrize("q", [1.0, 0.0, 0.6, 1.4])
def test_stair_points_on_curves_and_feed_rule(q: float) -> None:
    r = run({"q": q, "R_factor": 1.5})
    assert r["ok"]
    s = r["series"]
    px, py = s["stages"]["x"], s["stages"]["y"]
    n = int(out(r, "N_theoretical"))
    assert len(px) == 2 * n
    assert (px[0], py[0]) == (0.95, 0.95)
    rect, strip, qline = s["rectifying_line"], s["stripping_line"], s["q_line"]
    xi, yi = rect["x"][0], rect["y"][0]
    assert strip["x"][1] == xi and strip["y"][1] == yi
    assert qline["x"][0] == 0.5 and qline["y"][0] == 0.5
    sr = (rect["y"][1] - yi) / (rect["x"][1] - xi)
    ss = (yi - strip["y"][0]) / (xi - strip["x"][0])
    feed = int(out(r, "feed_stage"))
    for k in range(1, 2 * n, 2):  # horizontal step ends: on the equilibrium curve
        assert py[k] == pytest.approx(eq(px[k]), abs=1e-9)
    for k in range(2, 2 * n, 2):  # vertical step ends: on the operating line
        stage = k // 2
        assert px[k] == px[k - 1]
        if stage < feed:
            assert px[k] > xi
            assert py[k] == pytest.approx(yi + sr * (px[k] - xi), abs=1e-9)
        else:
            assert px[k] <= xi
            assert py[k] == pytest.approx(yi + ss * (px[k] - xi), abs=1e-9)
    stage_x = [px[2 * i - 1] for i in range(1, n + 1)]  # liquid x of each stage
    assert all(x > xi for x in stage_x[: feed - 1])
    assert stage_x[feed - 1] <= xi
    assert stage_x[-1] <= 0.05
    assert all(x > 0.05 for x in stage_x[:-1])


def test_real_trays_and_geometry() -> None:
    r = run({"Eo": 0.7})
    n = int(out(r, "N_theoretical"))
    assert out(r, "theoretical_trays") == n - 1
    real = math.ceil((n - 1) / 0.7)
    assert out(r, "real_trays") == real
    g = r["geometry"]
    assert g["type"] == "column"
    assert g["n_trays"] == real
    assert g["height_m"] == pytest.approx(real * 0.6)
    assert g["feed_tray"] == max(1, round(out(r, "feed_stage") / 0.7))
    assert g["diameter_m"] == out(r, "diameter_m")
    assert r["steady_states"] == [] and r["n_steady_states"] == 0


def test_diameter_matches_formula() -> None:
    r = run(series=False)
    rho_v = 101325 * 78.11 / (1000 * R_GAS * 353)
    u = 0.07 * math.sqrt((800 - rho_v) / rho_v)
    V = (out(r, "R") + 1) * 100 * 0.45 / 0.9
    assert out(r, "V") == pytest.approx(V)
    assert out(r, "V_bar") == pytest.approx(V)  # q = 1
    area = V * 78.11 / 3600 / rho_v / u
    assert out(r, "rho_V") == pytest.approx(rho_v)
    assert out(r, "u_max") == pytest.approx(u)
    assert out(r, "diameter_m") == pytest.approx(math.sqrt(4 * area / math.pi))
    assert out(r, "diameter_m") > 0


def test_diameter_sized_on_larger_vapour_flow() -> None:
    r = run({"q": 0.0}, series=False)  # V' = V - F < V
    assert out(r, "V_bar") == pytest.approx(out(r, "V") - 100)
    r2 = run({"q": 2.0}, series=False)  # V' = V + F > V
    assert out(r2, "V_bar") > out(r2, "V")
    rho_v = 101325 * 78.11 / (1000 * R_GAS * 353)
    u = 0.07 * math.sqrt((800 - rho_v) / rho_v)
    area = out(r2, "V_bar") * 78.11 / 3600 / rho_v / u
    assert out(r2, "diameter_m") == pytest.approx(math.sqrt(4 * area / math.pi))


@pytest.mark.parametrize(
    ("inp", "code", "field"),
    [
        ({"xB": 0.6}, "bad_compositions", "xB"),
        ({"zF": 0.97}, "bad_compositions", "xD"),
        ({"alpha": 1.0}, "bad_alpha", "alpha"),
        ({"alpha": 0.8}, "out_of_range", "alpha"),
        ({"q": 5}, "out_of_range", "q"),
        ({"xD": 1.0}, "out_of_range", "xD"),
        ({"Eo": 0}, "out_of_range", "Eo"),
        ({"bogus": 1}, "unknown_input", "bogus"),
        ({"F": "ten"}, "not_a_number", "F"),
        ({"P": {"value": 1, "unit": "bar"}}, "wrong_unit", "P"),
        ({"xD": 0.55, "alpha": 20}, "infeasible_separation", "xD"),
        ({"P": 1e8, "MW_top": 500, "T_top": 150}, "bad_vapour_density", "rho_L"),
    ],
)
def test_structured_errors(inp: dict[str, Any], code: str, field: str) -> None:
    r = run(inp, series=False)
    assert not r["ok"]
    assert {"code": code, "field": field}.items() <= r["errors"][0].items()
    assert r["errors"][0]["message"]
    json.dumps(r, allow_nan=False)


def test_series_shapes_and_size() -> None:
    r = run()
    assert set(r["series"]) == {
        "equilibrium",
        "diagonal",
        "rectifying_line",
        "stripping_line",
        "q_line",
        "stages",
    }
    for s in r["series"].values():
        assert len(s["x"]) == len(s["y"]) <= 200
        assert s["x_unit"] == s["y_unit"] == "-"
    assert r["series"]["q_line"]["x"][1] == pytest.approx(out(r, "x_star"))
    assert r["series"]["rectifying_line"]["x"][1] == 0.95
    assert r["series"]["stripping_line"]["x"][0] == 0.05
    assert len(json.dumps(run(series=False), allow_nan=False)) < 16384
    assert run(series=False)["series"] == {}


def test_series_thinned_for_many_stages() -> None:
    r = run({"alpha": 1.05, "R_factor": 10.0})
    assert r["ok"] and out(r, "N_theoretical") > 99
    assert len(r["series"]["stages"]["x"]) <= 200


def test_random_inputs_never_crash_and_stay_json_safe() -> None:
    rng = random.Random(11)
    for _ in range(300):
        xb = rng.uniform(0.001, 0.4)
        zf = rng.uniform(xb + 0.01, 0.8)
        xd = rng.uniform(zf + 0.01, 0.999)
        inp = {
            "xB": xb,
            "zF": zf,
            "xD": xd,
            "alpha": rng.uniform(1.05, 12),
            "q": rng.uniform(-2, 3),
            "R_factor": rng.uniform(1.0001, 6),
            "Eo": rng.uniform(0.2, 1),
        }
        r = run(inp)
        json.dumps(r, allow_nan=False)
        if r["ok"]:
            assert out(r, "N_theoretical") >= 1
            assert out(r, "diameter_m") > 0
        else:
            assert r["errors"][0]["code"] in {
                "too_many_stages",
                "infeasible_separation",
                "degenerate_operating_lines",
            }


def test_defaults_are_fast_and_match_spec() -> None:
    start = time.perf_counter()
    r = run()
    assert time.perf_counter() - start < 1.0
    assert r["ok"] and r["template"] == "mccabe"
    assert r["inputs"]["alpha"] == {"value": SPEC["alpha"]["default"], "unit": "-"}
    assert out(r, "R") == pytest.approx(1.3 * 1.1)
