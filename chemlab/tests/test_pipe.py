"""Pipe and pump tests. Reference numbers come from the `fluids` library (not a
dependency; absent in CI), generated once with:
  Re = fluids.core.Reynolds(V=Q/(pi D^2/4), D=D, rho=rho, mu=mu)
  f  = fluids.friction.friction_factor(Re=Re, eD=eps/D)   (Clamond exact Colebrook)
then heads/power by hand: h = f L/D u^2/2g + K u^2/2g + dz + dP/(rho g), g = 9.80665."""

import json
import math
import random
import time
from typing import Any

import pytest
from chemlab.pipe import SPEC, run

# default case: Q=0.01, D=0.1, L=100, eps=4.5e-5, water 25 C, K=5, dz=10, eta=0.7
DEF = {"Re": 142631.44113493903, "f": 0.019239964416490455, "head": 12.003556269369835}
DEF_PH, DEF_PS = 1173.6153106374863, 1676.5933009106948
SMOOTH_F = 0.016724990301417556  # same case, eps=0: friction_factor(Re, eD=0)
SMOOTH_HEAD = 11.795680875290081
TRANS = {"Q": 1e-4, "D": 0.05, "L": 50, "K_fittings": 2, "dz": 3, "eta": 0.6}
TRANS_F, TRANS_RE = 0.044986813523959404, 2852.628822698781  # fluids, same recipe
LAM = {**TRANS, "Q": 1e-5}  # Re = 285.26, f = 64/Re


def out(r: dict[str, Any], name: str) -> float:
    return float(r["outputs"][name]["value"])


def test_default_matches_fluids() -> None:
    r = run()
    assert r["ok"] and r["warnings"] == []
    assert out(r, "Re") == pytest.approx(DEF["Re"], rel=1e-6)
    assert out(r, "f_darcy") == pytest.approx(DEF["f"], rel=1e-6)
    assert out(r, "head") == pytest.approx(DEF["head"], rel=1e-6)
    assert out(r, "P_hydraulic") == pytest.approx(DEF_PH, rel=1e-6)
    assert out(r, "P_shaft") == pytest.approx(DEF_PS, rel=1e-6)
    assert out(r, "dP_friction") == pytest.approx(15548.541760092217, rel=1e-6)
    assert out(r, "u") == pytest.approx(0.01 / (math.pi * 0.05**2), rel=1e-12)


def test_smooth_pipe() -> None:
    r = run({"eps": 0})
    assert out(r, "f_darcy") == pytest.approx(SMOOTH_F, rel=1e-6)
    assert out(r, "head") == pytest.approx(SMOOTH_HEAD, rel=1e-6)


def test_laminar_is_64_over_re() -> None:
    r = run(LAM)
    re = 4 * 997 * 1e-5 / (math.pi * 0.05 * 8.9e-4)  # hand calc: 4 rho Q/(pi D mu)
    assert out(r, "Re") == pytest.approx(re, rel=1e-12) and re < 2300
    assert out(r, "f_darcy") == pytest.approx(64 / re, rel=1e-12)
    assert out(r, "f_darcy") == pytest.approx(0.22435446031654285, rel=1e-12)
    assert r["warnings"] == []


def test_transitional_warning() -> None:
    r = run(TRANS)
    assert out(r, "Re") == pytest.approx(TRANS_RE, rel=1e-9)
    assert out(r, "f_darcy") == pytest.approx(TRANS_F, rel=1e-6)
    assert any("transitional" in w for w in r["warnings"])


def test_negative_head_no_pump() -> None:
    r = run({"dz": -30})
    assert r["ok"]
    assert out(r, "head") == pytest.approx(-27.996443730630165, rel=1e-6)
    assert out(r, "P_hydraulic") == 0.0 and out(r, "P_shaft") == 0.0
    assert any("no pump needed" in w for w in r["warnings"])


def test_pressure_rise_adds_static_head() -> None:
    r = run({"dz": 0, "dP": 2.0e5})
    assert out(r, "h_static") == pytest.approx(2.0e5 / (997 * 9.80665), rel=1e-12)


def test_energy_balance_identity() -> None:
    rnd = random.Random(3)
    for _ in range(50):
        r = run({"Q": rnd.uniform(1e-4, 0.1), "dz": rnd.uniform(-5, 50), "dP": 1e4})
        s = out(r, "h_major") + out(r, "h_minor") + out(r, "h_static")
        assert out(r, "head") == pytest.approx(s, rel=1e-12, abs=1e-12)


def test_system_curve() -> None:
    r = run()
    c = r["series"]["head_curve"]
    assert len(c["x"]) == 60 and c["x_unit"] == "m^3/s" and c["y_unit"] == "m"
    assert c["x"][0] == 0.0 and c["x"][-1] == pytest.approx(0.02)
    assert c["y"][0] == pytest.approx(10.0)
    assert all(b > a for a, b in zip(c["y"], c["y"][1:], strict=False))
    assert r["geometry"] == {
        "type": "pipe",
        "diameter_m": 0.1,
        "length_m": 100.0,
        "dz_m": 10.0,
    }


def test_curve_matches_direct_runs_and_input_flow() -> None:
    full = run()
    xs, ys = full["series"]["head_curve"]["x"], full["series"]["head_curve"]["y"]
    for i in (1, 17, 59):
        assert ys[i] == pytest.approx(
            out(run({"Q": xs[i]}, series=False), "head"), rel=1e-12
        )
    # Q sits midway between grid points 29 and 30
    assert (ys[29] + ys[30]) / 2 == pytest.approx(out(full, "head"), rel=2e-3)


# fluids.friction.friction_factor(Re=re, eD=e_d), keyed (re, e_d)
FLUIDS_CORNERS = {
    (1e4, 0.01): 0.04312658470681169,
    (1e4, 0.05): 0.07380127563853829,
    (1e8, 0.0): 0.00594046635163676,
}


def churchill(re: float, e_d: float) -> float:
    a = (2.457 * math.log(1 / ((7 / re) ** 0.9 + 0.27 * e_d))) ** 16
    b = (37530 / re) ** 16
    return 8 * ((8 / re) ** 12 + 1 / (a + b) ** 1.5) ** (1 / 12)


@pytest.mark.parametrize("e_d", [0.0, 1e-5, 1e-4, 1e-3, 1e-2, 0.05])
@pytest.mark.parametrize("re", [1e4, 1e5, 1e6, 1e7, 1e8])
def test_colebrook_agrees_with_churchill(re: float, e_d: float) -> None:
    # D=0.1, mu=1e-3, rho=1000 -> Re = 1e5 * u ... pick u to hit Re exactly
    d, mu, rho = 0.1, 1e-3, 1000.0
    u = re * mu / (rho * d)
    q = u * math.pi * d * d / 4
    if not 1e-7 <= q <= 10:
        pytest.skip("flow outside SPEC range")
    r = run({"Q": q, "D": d, "eps": e_d * d, "rho": rho, "mu": mu}, series=False)
    assert out(r, "Re") == pytest.approx(re, rel=1e-9)
    f = out(r, "f_darcy")
    # Churchill is itself a fit: <1% almost everywhere, up to 2.1% at the corners
    # (Re 1e4 with eD 0.01/0.05, smooth Re 1e8), where Colebrook matches fluids exactly.
    assert f == pytest.approx(churchill(re, e_d), rel=0.025)
    if (re, e_d) in FLUIDS_CORNERS:
        assert f == pytest.approx(FLUIDS_CORNERS[(re, e_d)], rel=1e-9)
    else:
        assert f == pytest.approx(churchill(re, e_d), rel=0.01)


def test_validation_errors() -> None:
    cases = [
        ({"Q": 0}, "out_of_range", "Q"),
        ({"eta": 1.5}, "out_of_range", "eta"),
        ({"D": {"value": 0.1, "unit": "mm"}}, "wrong_unit", "D"),
        ({"bogus": 1}, "unknown_input", "bogus"),
        ({"D": 0.005, "eps": 0.0026}, "roughness_too_large", "eps"),
        ({"L": "x"}, "not_a_number", "L"),
    ]
    for inp, code, field in cases:
        r = run(inp)
        assert not r["ok"], inp
        assert (r["errors"][0]["code"], r["errors"][0]["field"]) == (code, field)
    assert run({"D": 0.005, "eps": 0.0024})["ok"]


def test_json_safe_and_fast() -> None:
    t = time.perf_counter()
    r = run()
    assert time.perf_counter() - t < 1.0
    json.dumps(r, allow_nan=False)


def test_random_sweep_never_raises() -> None:
    rnd = random.Random(11)
    for _ in range(2000):
        inp = {}
        for name, s in SPEC.items():
            lo, hi = s["min"], s["max"]
            if lo > 0 and hi / lo > 1e3:
                inp[name] = math.exp(rnd.uniform(math.log(lo), math.log(hi)))
            else:
                inp[name] = rnd.uniform(lo, hi)
        r = run(inp, series=rnd.random() < 0.2)
        json.dumps(r, allow_nan=False)
        assert r["ok"] or r["errors"][0]["code"] == "roughness_too_large"
