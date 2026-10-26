"""Textbook checks for the correlations module (Incropera, Kunii-Levenspiel, Swamee-Jain)."""

import math

import pytest
from chemlab._correlations import (
    annular_fin_efficiency,
    antoine_p,
    churchill_bernstein_nu,
    colebrook_f,
    dittus_boelter_nu,
    eps_ntu_counterflow,
    ergun_umf,
    fuller_diffusivity,
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
