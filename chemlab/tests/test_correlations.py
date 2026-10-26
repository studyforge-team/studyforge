"""Textbook checks for the correlations module (Incropera, Kunii-Levenspiel, Swamee-Jain)."""

import math

import pytest
from chemlab._correlations import (
    annular_fin_efficiency,
    antoine_p,
    bubble_p,
    bubble_t,
    churchill_bernstein_nu,
    colebrook_f,
    cubic_eos,
    cubic_psat,
    dew_p,
    dew_t,
    dittus_boelter_nu,
    eps_ntu_counterflow,
    ergun_umf,
    fuller_diffusivity,
    gamma_binary,
    ig_cp_integrals,
    kremser_stages,
    lee_kesler,
    lmtd,
    pitzer_virial,
    rachford_rice,
    rayleigh_residue,
    sieder_tate_nu,
    wilke_chang_diffusivity,
)


def test_annular_fin() -> None:
    eta = annular_fin_efficiency(0.0125, 0.030, 0.0015, 200, 80)
    assert eta == pytest.approx(0.9156, rel=0.005)


def test_ergun() -> None:
    u = ergun_umf(0.5e-3, 2500, 998, 1e-3, 0.43)
    assert u * 1000 == pytest.approx(3.313, rel=0.01)


def test_colebrook_vs_swamee_jain() -> None:
    Re, e = 2.54e5, 4.6e-4
    sj = 0.25 / math.log10(e / 3.7 + 5.74 / Re**0.9) ** 2
    assert colebrook_f(Re, e) == pytest.approx(sj, rel=0.02)


def test_churchill_bernstein() -> None:
    nu = churchill_bernstein_nu(8 * 0.025 / 2.1e-5, 0.71)
    assert nu * 0.0307 / 0.025 == pytest.approx(64.11, rel=0.01)


def test_pipe_nusselt() -> None:
    assert dittus_boelter_nu(1e4, 5) == pytest.approx(0.023 * 1e4**0.8 * 5**0.4)
    assert dittus_boelter_nu(1e4, 5, heating=False) < dittus_boelter_nu(1e4, 5)
    assert sieder_tate_nu(1e4, 5, 1.0) == pytest.approx(0.027 * 1e4**0.8 * 5 ** (1 / 3))


def test_eps_ntu() -> None:
    assert eps_ntu_counterflow(2.0, 1.0) == pytest.approx(2 / 3)
    assert eps_ntu_counterflow(1.0, 0.0) == pytest.approx(1 - math.exp(-1))
    assert eps_ntu_counterflow(1.0, 1 - 1e-9) == pytest.approx(0.5, rel=1e-6)


def test_lmtd_and_antoine() -> None:
    assert lmtd(40, 60) == pytest.approx((60 - 40) / math.log(60 / 40))
    assert lmtd(30, 30) == 30
    # water, A=8.07131 B=1730.63 C=233.426 (mmHg, degC): ~760 mmHg at 100 degC
    assert antoine_p(100, 8.07131, 1730.63, 233.426) == pytest.approx(760, rel=0.005)


def test_fuller_co2_n2() -> None:
    # Poling form; the older atm form (1e-3 T^1.75 sqrt(1/MA+1/MB)/...) gives 0.1643 cm2/s
    d = fuller_diffusivity(300.0, 101325.0, 44.01, 28.01, 26.9, 18.5)
    assert d == pytest.approx(0.1643e-4, rel=0.005)


def test_wilke_chang_acetic_acid_in_water() -> None:
    # Vb(acetic acid) 64.1 cm3/mol, water 0.89 mPa s at 25 C: ~1.4e-9 m2/s (exp. 1.29e-9)
    d = wilke_chang_diffusivity(298.15, 0.89e-3, 18.015, 64.1)
    assert d == pytest.approx(1.398e-9, rel=0.005)


def test_rayleigh_residue() -> None:
    # integral of dx/(y - x) with y = a x/(1 + (a-1) x), done numerically
    from scipy.integrate import quad

    a, xF, xW = 2.5, 0.5, 0.3
    integral = quad(lambda x: 1 / (a * x / (1 + (a - 1) * x) - x), xW, xF)[0]
    assert rayleigh_residue(100.0, xF, xW, a) == pytest.approx(100.0 * math.exp(-integral), rel=1e-9)
    assert rayleigh_residue(100.0, xF, xW, a) < 100.0


def test_rachford_rice() -> None:
    z, K = [0.3, 0.5, 0.2], [3.0, 1.1, 0.2]
    v = rachford_rice(z, K)
    assert sum(zi / (1 + v * (k - 1)) for zi, k in zip(z, K, strict=True)) == pytest.approx(1.0, abs=1e-10)
    assert rachford_rice([0.5, 0.5], [0.5, 0.8]) == 0.0  # subcooled
    assert rachford_rice([0.5, 0.5], [2.0, 3.0]) == 1.0  # superheated


def test_kremser_stages() -> None:
    # stage-by-stage count for y_in 0.02 -> y_out 0.001, pure solvent, m 1, A 1.4
    y_in, y_out, m, A = 0.02, 0.001, 1.0, 1.4
    n = kremser_stages(y_in, y_out, 0.0, m, A)
    # closed form check: fraction absorbed (A^(N+1) - A)/(A^(N+1) - 1)
    frac = (A ** (n + 1) - A) / (A ** (n + 1) - 1)
    assert 1 - y_out / y_in == pytest.approx(frac, rel=1e-9)


def test_lee_kesler_published_points() -> None:
    # SVNA Ex. 3.10 (n-butane, Tr = 1.2, Pr = 0.66): Z0 = 0.865, Z1 = 0.038 (Tables E.1/E.2)
    r = lee_kesler(1.2, 0.66, 0.2)
    assert r["Z0"] == pytest.approx(0.865, abs=0.003)
    assert r["Z1"] == pytest.approx(0.038, abs=0.003)
    assert r["Z"] == pytest.approx(r["Z0"] + 0.2 * r["Z1"])
    # Table E.1 (recalled, moderate confidence): Tr = 1.5, Pr = 1.0 -> 0.9103; Tr = 0.8, Pr = 1.0 -> 0.1626
    assert lee_kesler(1.5, 1.0, 0.0)["Z0"] == pytest.approx(0.9103, abs=0.003)
    assert lee_kesler(0.8, 1.0, 0.0)["Z0"] == pytest.approx(0.1626, abs=0.003)


@pytest.mark.parametrize("Tr,Pr", [(1.1, 3.0), (1.5, 1.0), (0.9, 0.4)])
def test_lee_kesler_thermodynamic_consistency(Tr: float, Pr: float) -> None:
    from scipy.integrate import quad

    om, h = 0.3, 1e-5

    def z(t: float, p: float) -> float:
        return lee_kesler(t, p, om)["Z"]

    def dzdt(p: float) -> float:
        return (z(Tr + h, p) - z(Tr - h, p)) / (2 * h)

    # integrate from a small Pr0 (Z - 1 ~ linear in P there, so the integrand is finite)
    p0 = 1e-4
    r = lee_kesler(Tr, Pr, om)
    hr = -(Tr**2) * quad(lambda p: dzdt(p) / p, p0, Pr, limit=200)[0]
    sr = -Tr * quad(lambda p: dzdt(p) / p, p0, Pr, limit=200)[0] - quad(lambda p: (z(Tr, p) - 1) / p, p0, Pr)[0]
    assert r["HR_RTc"] == pytest.approx(hr, rel=0.01)
    assert r["SR_R"] == pytest.approx(sr, rel=0.01)
    # ln phi = HR/(RT) - SR/R
    assert r["lnphi"] == pytest.approx(r["HR_RTc"] / Tr - r["SR_R"], abs=1e-6)


def test_lee_kesler_liquid_root() -> None:
    v, liq = lee_kesler(0.8, 0.1, 0.2), lee_kesler(0.8, 0.1, 0.2, phase="liquid")
    assert v["Z0"] > 0.9 and liq["Z0"] < 0.05


def test_pitzer_virial_consistency_and_limit() -> None:
    Tr, Pr, om, h = 1.3, 0.4, 0.25, 1e-4
    r = pitzer_virial(Tr, Pr, om)
    dz = (pitzer_virial(Tr + h, Pr, om)["Z"] - pitzer_virial(Tr - h, Pr, om)["Z"]) / (2 * h)
    assert r["HR_RTc"] == pytest.approx(-(Tr**2) * dz, rel=1e-5)  # Z linear in Pr
    assert r["SR_R"] == pytest.approx(-Tr * dz - (r["Z"] - 1), rel=1e-5)
    lk, pv = lee_kesler(1.5, 0.05, 0.2), pitzer_virial(1.5, 0.05, 0.2)
    assert pv["Z"] == pytest.approx(lk["Z"], rel=0.01)
    assert pv["HR_RTc"] == pytest.approx(lk["HR_RTc"], rel=0.05)


def test_ig_cp_integrals_vs_quad() -> None:
    from scipy.integrate import quad

    A, B, C, D = 3.4, 1.2e-3, 2.0e-7, 1.0e4
    cp = lambda t: A + B * t + C * t**2 + D / t**2
    r = ig_cp_integrals(298.15, 650.0, A, B, C, D)
    assert r["dH_R"] == pytest.approx(quad(cp, 298.15, 650.0)[0], rel=1e-9)
    assert r["dS_R"] == pytest.approx(quad(lambda t: cp(t) / t, 298.15, 650.0)[0], rel=1e-9)


def test_results_read_every_way_a_model_writes_them() -> None:
    import json

    r = lee_kesler(1.2, 0.66, 0.2)
    z, hr, sr, lnphi = r
    assert (z, hr, sr, lnphi) == (r["Z"], r.HR_RTc, r["SR_R"], r.lnphi)
    assert r["Z0"] == r.Z0
    assert json.loads(json.dumps(r))["Z"] == r["Z"]  # still a plain dict inside result
    dh, ds = ig_cp_integrals(300.0, 400.0, 3.5, 0.0)
    assert dh == pytest.approx(350.0)
    assert ds == pytest.approx(3.5 * math.log(4 / 3))
    assert pitzer_virial(1.5, 0.05, 0.2).Z == pitzer_virial(1.5, 0.05, 0.2)["Z"]


# ---- activity models ----
_MODELS = {
    "margules": (0.8, 1.3),
    "van_laar": (1.1, 0.7),
    "wilson": (0.19, 0.84),
    "nrtl": (0.6, 1.4, 0.3),
}


def _lng(model: str, x1: float, i: int) -> float:
    return math.log(list(gamma_binary(model, x1, _MODELS[model]))[i])


@pytest.mark.parametrize("model", list(_MODELS))
def test_gamma_pure_limits_and_gibbs_duhem(model: str) -> None:
    assert gamma_binary(model, 1.0, _MODELS[model]).gamma1 == pytest.approx(1.0)
    assert gamma_binary(model, 0.0, _MODELS[model]).gamma2 == pytest.approx(1.0)
    for x1 in (0.15, 0.5, 0.8):
        h = 1e-6
        d1 = (_lng(model, x1 + h, 0) - _lng(model, x1 - h, 0)) / (2 * h)
        d2 = (_lng(model, x1 + h, 1) - _lng(model, x1 - h, 1)) / (2 * h)
        assert x1 * d1 + (1 - x1) * d2 == pytest.approx(0.0, abs=1e-7)


def test_gamma_infinite_dilution() -> None:
    a12, a21 = _MODELS["margules"]
    assert math.log(gamma_binary("margules", 0.0, (a12, a21)).gamma1) == pytest.approx(a12)
    assert math.log(gamma_binary("margules", 1.0, (a12, a21)).gamma2) == pytest.approx(a21)
    assert math.log(gamma_binary("van_laar", 0.0, _MODELS["van_laar"]).gamma1) == pytest.approx(1.1)
    l12, l21 = _MODELS["wilson"]
    assert math.log(gamma_binary("wilson", 0.0, (l12, l21)).gamma1) == pytest.approx(-math.log(l12) + 1 - l21)
    assert math.log(gamma_binary("wilson", 1.0, (l12, l21)).gamma2) == pytest.approx(-math.log(l21) + 1 - l12)


def test_wilson_ethanol_water_like() -> None:
    l12, l21, x1 = 0.19, 0.84, 0.3
    x2 = 1 - x1
    ln1 = -math.log(x1 + l12 * x2) + x2 * (l12 / (x1 + l12 * x2) - l21 / (x2 + l21 * x1))
    r = gamma_binary("wilson", x1, (l12, l21))
    assert r.gamma1 == pytest.approx(math.exp(ln1), rel=1e-12)
    assert r.gamma1 > 1.5  # strongly positive deviation
    g1, g2 = r  # unpacks in order
    assert (g1, g2) == (r["gamma1"], r["gamma2"])


def test_gamma_unknown_model() -> None:
    with pytest.raises(ValueError):
        gamma_binary("uniquac", 0.5, (1.0, 1.0))


# ---- cubic EOS ----
PROPANE = (369.83, 42.48e5, 0.152)


def test_cubic_pr_propane_vapour() -> None:
    r = cubic_eos(300.0, 1e5, *PROPANE, eos="PR")
    assert r.Z_vap == pytest.approx(0.99, abs=0.01)
    assert r.Z_vap < 1.0
    assert r.V_vap == pytest.approx(r.Z_vap * 8.314 * 300 / 1e5)
    assert r.Z_liq < 0.01  # metastable liquid root below Psat (~10 bar)
    sc = cubic_eos(400.0, 1e5, *PROPANE)  # supercritical: one root
    assert sc.Z_liq == pytest.approx(sc.Z_vap)


def test_cubic_lnphi_matches_integration() -> None:
    from scipy.integrate import quad

    p_end = 2e5
    exact, _ = quad(lambda p: (cubic_eos(300.0, p, *PROPANE).Z_vap - 1) / p, 1.0, p_end, epsabs=1e-12)
    assert cubic_eos(300.0, p_end, *PROPANE).lnphi_vap == pytest.approx(exact, rel=2e-3)


def test_cubic_vdw_critical_point() -> None:
    r = cubic_eos(150.0, 50e5, 150.0, 50e5, 0.0, "vdW")
    assert r.Z_vap == pytest.approx(3 / 8, abs=1e-5)
    assert r.B == pytest.approx(1 / 8)
    assert r.A == pytest.approx(27 / 64)


def test_cubic_unknown_eos() -> None:
    with pytest.raises(ValueError):
        cubic_eos(300.0, 1e5, *PROPANE, eos="foo")


@pytest.mark.parametrize("eos", ["vdW", "RK", "SRK", "PR"])
def test_cubic_psat_equal_fugacity(eos: str) -> None:
    r = cubic_psat(300.0, *PROPANE, eos=eos)
    e = cubic_eos(300.0, r.Psat, *PROPANE, eos=eos)
    assert e.lnphi_vap == pytest.approx(e.lnphi_liq, abs=1e-9)
    assert e.Z_vap > e.Z_liq


def test_cubic_psat_pr_propane() -> None:
    assert cubic_psat(300.0, *PROPANE, eos="PR").Psat == pytest.approx(9.99e5, rel=0.01)


def test_cubic_psat_above_tc() -> None:
    with pytest.raises(ValueError):
        cubic_psat(400.0, *PROPANE)


# ---- bubble / dew ----
def _benz(t: float) -> float:
    return antoine_p(t, 6.90565, 1211.033, 220.79)


def _tol(t: float) -> float:
    return antoine_p(t, 6.95464, 1344.8, 219.482)


def test_bubble_dew_ideal_benzene_toluene() -> None:
    x, p = [0.4, 0.6], 760.0
    b = bubble_t(x, p, [_benz, _tol], T0=90.0)
    assert x[0] * _benz(b.T) + x[1] * _tol(b.T) == pytest.approx(p, rel=1e-9)
    assert sum(b.y) == pytest.approx(1.0)
    d = dew_t(b.y, p, [_benz, _tol])  # default T0 (300) still brackets
    assert d.T == pytest.approx(b.T, abs=1e-6)
    assert d.x == pytest.approx(x, abs=1e-8)
    y = [0.5, 0.5]
    d2 = dew_t(y, p, [_benz, _tol], T0=90.0)
    assert y[0] / _benz(d2.T) + y[1] / _tol(d2.T) == pytest.approx(1 / p, rel=1e-9)
    assert d2.T > bubble_t(y, p, [_benz, _tol]).T


def test_bubble_dew_with_gamma() -> None:
    def gam(x, t):
        return list(gamma_binary("margules", x[0], (0.5, 0.7)))

    x, p = [0.3, 0.7], 760.0
    b = bubble_t(x, p, [_benz, _tol], gamma=gam, T0=90.0)
    g = gam(x, b.T)
    assert sum(xi * gi * f(b.T) for xi, gi, f in zip(x, g, (_benz, _tol), strict=True)) == pytest.approx(p, rel=1e-9)
    d = dew_t(b.y, p, [_benz, _tol], gamma=gam, T0=90.0)
    assert d.T == pytest.approx(b.T, abs=1e-6)
    assert d.x == pytest.approx(x, abs=1e-6)


def test_bubble_dew_pressure() -> None:
    ps = [1.2e5, 0.4e5]
    b = bubble_p([0.5, 0.5], ps)
    assert b.P == pytest.approx(0.8e5)
    assert b.y == pytest.approx([0.75, 0.25])
    d = dew_p(b.y, ps)
    assert d.P == pytest.approx(b.P)
    assert d.x == pytest.approx([0.5, 0.5])

    def gm(x):
        return list(gamma_binary("wilson", x[0], (0.19, 0.84)))

    bg = bubble_p([0.3, 0.7], ps, gm)
    dg = dew_p(bg.y, ps, gm)
    assert dg.P == pytest.approx(bg.P, rel=1e-8)
    assert dg.x == pytest.approx([0.3, 0.7], abs=1e-6)
