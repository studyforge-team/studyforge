"""Heat exchanger template tests.

Reference areas come from the `ht` library 1.2.0 (MIT), run once outside CI because
neither CI nor the browser sandbox has it:
    ht.effectiveness_NTU_method(mh, mc, Cph, Cpc, subtype, Thi, Tho, Tci)["UA"] / U
with subtype "counterflow", "parallel" and "S&T" (1 shell pass, 2 tube passes), and
    Q / (U * ht.LMTD(Thi, Tho, Tci, Tco) * ht.F_LMTD_Fakheri(Thi, Tho, Tci, Tco, shells=1))
for the 1-2 exchanger (ht's S&T e-NTU divides by zero when Ch == Cc).
Case 1 is golden proposal P1-05 (docs/golden-proposals/p1_problems.md), 7.43518 m^2.
"""

import json
import math
import random

import numpy as np
import pytest
from chemlab.hx import SPEC, run
from scipy.integrate import solve_ivp

C = 273.15
# (inputs, Q W, Tc_out K, A_counter, A_co, A_shell12, F) ; areas in m^2
CASES = [
    (
        {
            "mh": 2.0,
            "cph": 2100,
            "Th_in": 160 + C,
            "Th_out": 100 + C,
            "mc": 2.5,
            "cpc": 4180,
            "Tc_in": 20 + C,
            "U": 350,
        },
        252000.0,
        317.26483253588515,
        7.435179289717791,
        7.860768917492417,
        7.637228669053519,
        0.9735441495742503,
    ),
    (  # equal heat capacity rates (Cr = 1): counter-flow LMTD is the constant 40 K
        {
            "mh": 1.0,
            "cph": 4180,
            "Th_in": 90 + C,
            "Th_out": 60 + C,
            "mc": 1.0,
            "cpc": 4180,
            "Tc_in": 20 + C,
            "U": 500,
        },
        125400.0,
        323.15,
        6.27,
        8.133904423051208,
        6.982611484572041,
        0.8979448468317986,
    ),
    (
        {
            "mh": 0.5,
            "cph": 2000,
            "Th_in": 400,
            "Th_out": 320,
            "mc": 1.2,
            "cpc": 4180,
            "Tc_in": 290,
            "U": 250,
        },
        80000.0,
        305.94896331738437,
        5.7086486321160965,
        6.862929178507632,
        6.186651913211128,
        0.9227363543640958,
    ),
]


def out(r: dict, name: str) -> float:
    return r["outputs"][name]["value"]


@pytest.mark.parametrize("inp,q,tco,a_ct,a_co,a_12,f", CASES)
def test_matches_ht_library(inp, q, tco, a_ct, a_co, a_12, f) -> None:
    r = run(inp, series=False)
    assert r["ok"], r["errors"]
    assert out(r, "Q") == pytest.approx(q, rel=1e-9)
    assert out(r, "Tc_out") == pytest.approx(tco, rel=1e-9)
    assert out(r, "A_counter") == pytest.approx(a_ct, rel=1e-6)
    assert out(r, "A_co") == pytest.approx(a_co, rel=1e-6)
    assert out(r, "A_shell12") == pytest.approx(a_12, rel=1e-6)
    assert out(r, "F") == pytest.approx(f, rel=1e-6)
    assert not any("disagree" in w for w in r["warnings"])


def test_golden_p1_05_within_1_percent() -> None:
    r = run(CASES[0][0], series=False)
    assert out(r, "A_counter") == pytest.approx(7.43518, rel=0.01)
    assert r["outputs"]["A_counter"]["unit"] == "m^2"


def test_hand_calculation_case_1() -> None:
    # Q = 2.0*2100*60 = 252 kW; Tc_out = 20 + 252000/(2.5*4180) = 44.1148 C
    # counter: dT1 = 160-44.1148, dT2 = 100-20 -> LMTD = 96.837 K; A = Q/(U LMTD)
    tco = 20 + 252000 / (2.5 * 4180)
    d1, d2 = 160 - tco, 80.0
    lmtd = (d1 - d2) / math.log(d1 / d2)
    r = run(CASES[0][0], series=False)
    assert out(r, "LMTD_counter") == pytest.approx(lmtd, rel=1e-12)
    assert out(r, "A_counter") == pytest.approx(252000 / (350 * lmtd), rel=1e-12)


def test_ordering_counter_smallest_area() -> None:
    for inp, *_ in CASES:
        r = run(inp, series=False)
        assert out(r, "A_counter") < out(r, "A_shell12") < out(r, "A_co")
        assert 0 < out(r, "F") <= 1


def test_co_current_infeasible_is_a_warning_not_a_failure() -> None:
    # cold outlet would be above the hot outlet: only counter-flow (and maybe 1-2) works
    r = run(
        {
            "mh": 1.0,
            "cph": 4180,
            "Th_in": 90 + C,
            "Th_out": 40 + C,
            "mc": 1.0,
            "cpc": 4180,
            "Tc_in": 20 + C,
        }
    )
    assert r["ok"]
    assert "A_co" not in r["outputs"]
    assert any("co-current" in w for w in r["warnings"])
    assert out(r, "A_counter") > 0


def test_shell12_infeasible_drops_geometry() -> None:
    # strong temperature cross: no 1-shell-pass exchanger can do this duty
    r = run(
        {
            "mh": 1.0,
            "cph": 4180,
            "Th_in": 90 + C,
            "Th_out": 30 + C,
            "mc": 1.0,
            "cpc": 4180,
            "Tc_in": 20 + C,
        }
    )
    assert r["ok"]
    assert "A_shell12" not in r["outputs"] and "F" not in r["outputs"]
    assert r["geometry"] == {}
    assert any("1-2" in w for w in r["warnings"])


def test_low_f_warns() -> None:
    r = run(
        {
            "mh": 1.0,
            "cph": 4180,
            "Th_in": 90 + C,
            "Th_out": 50 + C,
            "mc": 1.0,
            "cpc": 4180,
            "Tc_in": 20 + C,
        }
    )
    assert r["ok"] and out(r, "F") < 0.75
    assert any("F below 0.75" in w for w in r["warnings"])


@pytest.mark.parametrize(
    "over,code,field",
    [
        ({"Th_out": 170 + C}, "no_cooling", "Th_out"),
        ({"Tc_in": 170 + C}, "hot_not_hotter", "Tc_in"),
        ({"Tc_in": 110 + C}, "temperature_cross", "Th_out"),  # Th_out below Tc_in
        ({"mc": 0.1}, "temperature_cross", "Th_out"),  # cold outlet above hot inlet
        ({"U": 0}, "out_of_range", "U"),
        ({"bogus": 1}, "unknown_input", "bogus"),
        ({"U": {"value": 0.35, "unit": "kW/(m^2 K)"}}, "wrong_unit", "U"),
    ],
)
def test_errors(over, code, field) -> None:
    r = run({**CASES[0][0], **over})
    assert not r["ok"]
    assert r["errors"][0]["code"] == code and r["errors"][0]["field"] == field
    json.dumps(r, allow_nan=False)


def test_geometry_shell_and_tube() -> None:
    r = run(CASES[0][0])
    g = r["geometry"]
    a12, do, lt = 7.637228669053519, 0.01905, 4.88
    n = math.ceil(a12 / (math.pi * do * lt))
    n += n % 2  # even, for 2 tube passes
    assert g["type"] == "shell_and_tube" and g["tube_passes"] == 2
    assert g["n_tubes"] == n == 28
    # Coulson & Richardson vol. 6 eq. 12.3b, triangular pitch 1.25 do, 2 passes
    # by hand: 28/0.249 = 112.45, ln = 4.7225, /2.207 = 2.1398, exp = 8.498, x 0.01905
    assert g["bundle_diameter_m"] == pytest.approx(0.16189, rel=1e-4)
    assert g["shell_diameter_m"] == pytest.approx(g["bundle_diameter_m"] + 0.015)
    assert g["tube_length_m"] == lt and g["tube_od_m"] == do
    assert g["pitch_m"] == pytest.approx(1.25 * do)
    assert out(r, "A_installed") >= a12


def test_profile_matches_ode_integration() -> None:
    inp, _q, tco, a_ct, *_ = CASES[2]
    r = run(inp)
    hot, cold = r["series"]["hot_profile"], r["series"]["cold_profile"]
    ch, cc, u = 0.5 * 2000, 1.2 * 4180, 250.0

    # march along the area from the hot inlet end; cold flows the other way
    def rhs(a: float, y: np.ndarray) -> list[float]:
        d = y[0] - y[1]
        return [-u * d / ch, -u * d / cc]

    sol = solve_ivp(
        rhs, (0, a_ct), [400.0, tco], rtol=1e-10, atol=1e-10, dense_output=True
    )
    for x, th, tc in zip(hot["x"], hot["y"], cold["y"], strict=True):
        yh, yc = sol.sol(x * a_ct)
        assert th == pytest.approx(yh, abs=1e-6) and tc == pytest.approx(yc, abs=1e-6)
    assert hot["y"][-1] == pytest.approx(320.0) and cold["y"][-1] == pytest.approx(
        290.0
    )
    assert hot["x_unit"] == "-" and hot["y_unit"] == "K"


def test_profile_equal_capacity_rates_is_linear() -> None:
    r = run(CASES[1][0])
    hot, cold = r["series"]["hot_profile"]["y"], r["series"]["cold_profile"]["y"]
    diffs = [h - c for h, c in zip(hot, cold, strict=True)]
    assert max(diffs) - min(diffs) < 1e-9 and diffs[0] == pytest.approx(40.0)


def test_random_inputs_stay_json_safe_and_consistent() -> None:
    rng = random.Random(7)
    n_ok = 0
    for _ in range(3000):
        inp = {
            k: rng.uniform(s["min"], min(s["max"], 10 * s["default"]))
            for k, s in SPEC.items()
        }
        r = run(inp, series=rng.random() < 0.1)
        json.dumps(r, allow_nan=False)
        assert not any("disagree" in w for w in r["warnings"])
        if r["ok"]:
            n_ok += 1
            o = r["outputs"]
            # independent counter-flow e-NTU (written here, not imported)
            ch, cc = inp["mh"] * inp["cph"], inp["mc"] * inp["cpc"]
            cmin, cr = min(ch, cc), min(ch, cc) / max(ch, cc)
            eps = o["Q"]["value"] / (cmin * (inp["Th_in"] - inp["Tc_in"]))
            if abs(1 - cr) > 1e-3:
                ntu = math.log((1 - eps * cr) / (1 - eps)) / (1 - cr)
                assert o["A_counter"]["value"] == pytest.approx(
                    ntu * cmin / inp["U"], rel=1e-7
                )
            if "A_shell12" in o:
                assert o["A_counter"]["value"] <= o["A_shell12"]["value"] * (1 + 1e-9)
    assert n_ok > 300


# Cc = Ch * mc for CASES[1] with mc near 1: 50-digit Decimal evaluation of the textbook
# formulas (A_counter, F, A_shell12); float textbook forms lose up to 1e-4 here
NEAR_EQUAL = [
    (1.001, 6.267652271519457, 0.898140357262213, 6.978477496128826),
    (0.999, 6.272354782247061, 0.8977485820170014, 6.9867610017882225),
    (1.0000001, 6.269999764875036, 0.897944866420484, 6.982611070398345),
    (0.9999999, 6.2700002351250355, 0.8979448272431058, 6.982611898745892),
    (1.0000000001, 6.269999999764875, 0.8979448468513873, 6.982611484157868),
    (0.9999999999, 6.270000000235125, 0.89794484681221, 6.982611484986215),
]


@pytest.mark.parametrize("mc,a_ct,f,a_12", NEAR_EQUAL)
def test_near_equal_capacity_rates_are_accurate(mc, a_ct, f, a_12) -> None:
    r = run({**CASES[1][0], "mc": mc}, series=False)
    assert out(r, "A_counter") == pytest.approx(a_ct, rel=1e-10)
    assert out(r, "F") == pytest.approx(f, rel=1e-10)
    assert out(r, "A_shell12") == pytest.approx(a_12, rel=1e-10)
    assert not any("disagree" in w for w in r["warnings"])


def test_no_disagreement_warnings_near_equal_rates() -> None:
    rng = random.Random(3)
    for _ in range(3000):
        d = rng.choice([-1, 1]) * 10 ** rng.uniform(-16, -2)
        r = run(
            {**CASES[rng.randrange(3)][0], "mc": 1.0 + d, "cpc": 4180}, series=False
        )
        if r["ok"]:
            assert not any("disagree" in w for w in r["warnings"]), (d, r["warnings"])


def test_spec_defaults_run() -> None:
    r = run({})
    assert r["ok"] and r["template"] == "hx"
    assert set(r["inputs"]) == set(SPEC)
