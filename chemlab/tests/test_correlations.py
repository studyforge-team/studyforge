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
    lmtd,
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
