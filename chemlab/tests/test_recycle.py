"""Recycle flowsheet tests. Expected values come from hand-derived closed forms
written here and from brute-force successive substitution, not template helpers."""

import json
import random
import time
from typing import Any

import pytest
from chemlab.recycle import SPEC, run


def out(r: dict[str, Any], name: str) -> float:
    return float(r["outputs"][name]["value"])


def substitution(f0: float, yi0: float, x: float, sa: float, si: float, p: float):
    """Iterate the loop: mixer -> reactor -> separator -> splitter -> mixer."""
    ra = ri = 0.0
    for _ in range(100000):
        ina, ini = f0 * (1 - yi0) + ra, f0 * yi0 + ri
        na, ni = (1 - x) * ina * sa * (1 - p), ini * si * (1 - p)
        if abs(na - ra) + abs(ni - ri) < 1e-13 * (1 + na + ni):
            ra, ri = na, ni
            break
        ra, ri = na, ni
    return ra, ri


def test_hand_calc_no_inert_no_purge() -> None:
    # F0=100, Xsp=0.5, sA=1, p=0: R_A = 100 (reactor feed 200, 100 B out, 100 recycled)
    r = run({"yI0": 0, "Xsp": 0.5, "sA": 1, "p": 0}, series=False)
    assert r["ok"] and r["errors"] == []
    assert out(r, "R_A") == pytest.approx(100.0, rel=1e-9)
    assert out(r, "reactor_in_A") == pytest.approx(200.0, rel=1e-9)
    assert out(r, "prod_B") == pytest.approx(100.0, rel=1e-9)
    assert out(r, "X_overall") == pytest.approx(1.0, rel=1e-9)
    assert out(r, "recycle_ratio") == pytest.approx(1.0, rel=1e-9)
    assert out(r, "prod_A") == pytest.approx(0.0, abs=1e-9)


def test_hand_calc_with_inert_and_purge() -> None:
    # F0=100, yI0=0.1 -> F0A=90, F0I=10; Xsp=.5, sA=sI=1, p=.1
    # A: a=.5*.9=.45, R_A=90*.45/.55=810/11=73.636; I: b=.9, R_I=10*.9/.1=90
    # reactor in: A=90+810/11=1800/11, I=100; purge = .1*overhead
    # P_A=.1*.5*1800/11=900/110... =8.1818, P_I=.1*100=10, yI=100/(1800/11+100)
    r = run({"yI0": 0.1, "Xsp": 0.5, "sA": 1, "sI": 1, "p": 0.1}, series=False)
    assert out(r, "R_A") == pytest.approx(810 / 11, rel=1e-9)
    assert out(r, "R_I") == pytest.approx(90.0, rel=1e-9)
    assert out(r, "P_A") == pytest.approx(90 / 11, rel=1e-9)
    assert out(r, "P_I") == pytest.approx(10.0, rel=1e-9)
    assert out(r, "prod_B") == pytest.approx(900 / 11, rel=1e-9)
    assert out(r, "X_overall") == pytest.approx(10 / 11, rel=1e-9)
    assert out(r, "yI_reactor_in") == pytest.approx(100 / (1800 / 11 + 100), rel=1e-9)
    assert out(r, "R_total") == pytest.approx(810 / 11 + 90, rel=1e-9)


def test_default_matches_closed_form_and_substitution() -> None:
    r = run(series=False)
    a = 0.7 * 0.95 * 0.95  # (1-Xsp) sA (1-p)
    ra = a * 99 / (1 - a)
    ri = 0.95 * 1.0 / (1 - 0.95)
    assert out(r, "R_A") == pytest.approx(ra, rel=1e-9)
    assert out(r, "R_I") == pytest.approx(ri, rel=1e-9)
    sa, si = substitution(100, 0.01, 0.3, 0.95, 1.0, 0.05)
    assert out(r, "R_A") == pytest.approx(sa, rel=1e-8)
    assert out(r, "R_I") == pytest.approx(si, rel=1e-8)
    assert out(r, "balance_error") < 0.005


def test_full_purge_means_no_recycle() -> None:
    r = run({"p": 1.0}, series=False)
    assert out(r, "R_total") == 0.0
    assert out(r, "X_overall") == pytest.approx(0.3, rel=1e-12)
    assert out(r, "reactor_in_A") == pytest.approx(99.0, rel=1e-12)
    assert out(r, "yI_reactor_in") == pytest.approx(0.01, rel=1e-12)


def test_inert_can_leave_with_product_when_sI_below_one() -> None:
    r = run({"p": 0, "sI": 0.9}, series=False)
    assert r["ok"]
    b = 0.9  # sI (1-p)
    assert out(r, "R_I") == pytest.approx(b * 1.0 / (1 - b), rel=1e-9)
    assert out(r, "prod_I") == pytest.approx(1.0, rel=1e-9)  # inert in = out


def test_no_inert_no_purge_is_fine() -> None:
    assert run({"p": 0, "yI0": 0})["ok"]


def test_inert_accumulates_error() -> None:
    r = run({"p": 0, "sI": 1, "yI0": 0.05})
    assert not r["ok"]
    assert r["errors"][0]["code"] == "inert_accumulates"
    assert r["errors"][0]["field"] == "p"


def test_large_recycle_warning() -> None:
    r = run({"Xsp": 1e-4, "sA": 1, "p": 0, "yI0": 0}, series=False)
    assert r["ok"]
    assert out(r, "recycle_ratio") == pytest.approx(0.9999 / 1e-4 * 1.0, rel=1e-6)
    assert any("recycle ratio" in w for w in r["warnings"])


def test_validation_errors() -> None:
    assert run({"p": 1.5})["errors"][0]["code"] == "out_of_range"
    assert run({"Xsp": 0})["errors"][0]["code"] == "out_of_range"
    assert run({"F0": {"value": 5, "unit": "mol/h"}})["errors"][0]["code"] == (
        "wrong_unit"
    )
    assert run({"foo": 1})["errors"][0]["code"] == "unknown_input"
    assert run({"sA": "x"})["errors"][0]["code"] == "not_a_number"
    assert not run({"p": -0.1})["ok"]
    assert run({"F0": {"value": 50, "unit": "kmol/h"}})["ok"]


def test_balance_closes_across_random_sweep() -> None:
    rng = random.Random(7)
    n = 0
    while n < 2000:
        inp = {
            "F0": rng.uniform(0.01, 1e4),
            "yI0": rng.uniform(0, 0.5),
            "Xsp": rng.uniform(0.01, 1),
            "sA": rng.uniform(0, 1),
            "sI": rng.choice([1.0, rng.uniform(0, 1)]),
            "p": rng.uniform(0.01, 1),
        }
        r = run(inp, series=False)
        assert r["ok"], inp
        assert out(r, "balance_error") < 5e-3
        assert out(r, "balance_error") < 1e-6
        n += 1


def test_random_cases_match_substitution() -> None:
    rng = random.Random(11)
    for _ in range(25):
        f0, yi0 = rng.uniform(1, 500), rng.uniform(0, 0.5)
        x, sa = rng.uniform(0.2, 1), rng.uniform(0, 1)
        si, p = rng.uniform(0, 1), rng.uniform(0.2, 1)
        r = run({"F0": f0, "yI0": yi0, "Xsp": x, "sA": sa, "sI": si, "p": p})
        ra, ri = substitution(f0, yi0, x, sa, si, p)
        assert out(r, "R_A") == pytest.approx(ra, rel=1e-7, abs=1e-9)
        assert out(r, "R_I") == pytest.approx(ri, rel=1e-7, abs=1e-9)


def test_series_monotonic_and_matches_point_runs() -> None:
    r = run()
    sw, ib = r["series"]["purge_sweep"], r["series"]["inert_buildup"]
    assert len(sw["x"]) == len(sw["y"]) == len(ib["y"]) == 60
    assert sw["x"][0] == pytest.approx(1e-3) and sw["x"][-1] == pytest.approx(1.0)
    assert sw["y"] == sorted(sw["y"], reverse=True)  # more purge -> less conversion
    assert ib["y"] == sorted(ib["y"], reverse=True)
    assert sw["y"][-1] == pytest.approx(0.3, rel=1e-9)
    for i in (0, 20, 59):
        pt = run({"p": sw["x"][i]}, series=False)
        assert out(pt, "X_overall") == pytest.approx(sw["y"][i], rel=1e-8)
        assert out(pt, "yI_reactor_in") == pytest.approx(ib["y"][i], rel=1e-8)
    assert sw["x_unit"] == "-" and ib["y_unit"] == "-"


def test_envelope_json_safe_and_fast() -> None:
    t0 = time.perf_counter()
    r = run()
    assert time.perf_counter() - t0 < 1.0
    json.dumps(r, allow_nan=False)
    assert r["template"] == "recycle"
    assert r["geometry"] == {
        "type": "flowsheet",
        "units": ["mixer", "reactor", "separator", "splitter"],
    }
    assert set(SPEC) == {"F0", "yI0", "Xsp", "sA", "sI", "p"}
    assert r["n_steady_states"] == 0
