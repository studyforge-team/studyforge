"""Textbook correlations as pure functions (numpy/scipy only, SI unless stated).

Not a template (no SPEC/run; the leading underscore keeps it out of discovery).
In the sandbox: `from chemlab._correlations import annular_fin_efficiency, ...`
"""

import math

from scipy.special import iv, kv


def annular_fin_efficiency(r1: float, r2: float, t: float, k: float, h: float) -> float:
    """Efficiency [-] of an annular fin of constant thickness, adiabatic tip.

    r1 root radius [m], r2 tip radius [m], t thickness [m], k conductivity [W/m/K],
    h coefficient [W/m2/K]. Exact Bessel solution (Incropera Eq. 3.96 / Table 3.5)
    using the corrected tip radius r2c = r2 + t/2 to account for the tip.
    """
    r2c = r2 + t / 2.0
    m = math.sqrt(2.0 * h / (k * t))
    num = kv(1, m * r1) * iv(1, m * r2c) - iv(1, m * r1) * kv(1, m * r2c)
    den = iv(0, m * r1) * kv(1, m * r2c) + kv(0, m * r1) * iv(1, m * r2c)
    return float(2.0 * r1 / (m * (r2c**2 - r1**2)) * num / den)


def ergun_umf(
    d: float, rho_p: float, rho: float, mu: float, eps: float, g: float = 9.81
) -> float:
    """Minimum fluidisation velocity [m/s] from the Ergun equation.

    d particle diameter [m], rho_p particle and rho fluid density [kg/m3], mu viscosity
    [Pa s], eps bed voidage at minimum fluidisation [-]. Solves
    150(1-e)^2 mu u/(e^3 d^2) + 1.75(1-e) rho u^2/(e^3 d) = (1-e)(rho_p-rho) g
    (Ergun pressure gradient per unit height = weight of bed minus buoyancy).
    """
    a = 1.75 * (1 - eps) * rho / (eps**3 * d)
    b = 150 * (1 - eps) ** 2 * mu / (eps**3 * d**2)
    c = (1 - eps) * (rho_p - rho) * g
    return float((-b + math.sqrt(b * b + 4 * a * c)) / (2 * a))


def colebrook_f(Re: float, rel_rough: float) -> float:
    """Darcy friction factor [-] from the Colebrook-White equation (iterative).

    Re Reynolds number [-], rel_rough = roughness / diameter [-].
    1/sqrt(f) = -2 log10(rel_rough/3.7 + 2.51/(Re sqrt(f))). Turbulent flow only.
    """
    x = 1.0 / math.sqrt(0.02)
    for _ in range(100):
        new = -2.0 * math.log10(rel_rough / 3.7 + 2.51 * x / Re)
        if abs(new - x) < 1e-12:
            x = new
            break
        x = new
    return float(1.0 / x**2)


def churchill_bernstein_nu(Re: float, Pr: float) -> float:
    """Average Nusselt number [-] for cross flow over a cylinder (Churchill-Bernstein).

    Valid for Re*Pr > 0.2; Re and Pr at film temperature, Re based on diameter.
    Incropera Eq. 7.57.
    """
    return float(
        0.3
        + 0.62
        * Re**0.5
        * Pr ** (1 / 3)
        / (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25
        * (1 + (Re / 282000.0) ** (5 / 8)) ** (4 / 5)
    )


def dittus_boelter_nu(Re: float, Pr: float, heating: bool = True) -> float:
    """Nusselt number [-] in turbulent pipe flow: 0.023 Re^0.8 Pr^n.

    n = 0.4 when the fluid is heated, 0.3 when cooled (Incropera Eq. 8.60).
    Re > 10000, 0.6 < Pr < 160.
    """
    return float(0.023 * Re**0.8 * Pr ** (0.4 if heating else 0.3))


def sieder_tate_nu(Re: float, Pr: float, mu_ratio: float) -> float:
    """Nusselt number [-] in turbulent pipe flow: 0.027 Re^0.8 Pr^(1/3) (mu/mu_s)^0.14.

    mu_ratio = bulk viscosity / wall viscosity [-] (Incropera Eq. 8.61).
    """
    return float(0.027 * Re**0.8 * Pr ** (1 / 3) * mu_ratio**0.14)


def eps_ntu_counterflow(NTU: float, Cr: float) -> float:
    """Effectiveness [-] of a counterflow heat exchanger (Incropera Eq. 11.30).

    NTU = UA/Cmin [-], Cr = Cmin/Cmax [-]. Cr = 1 gives NTU/(1+NTU).
    """
    if abs(1.0 - Cr) < 1e-12:
        return float(NTU / (1.0 + NTU))
    e = math.exp(-NTU * (1.0 - Cr))
    return float((1.0 - e) / (1.0 - Cr * e))


def lmtd(dt1: float, dt2: float) -> float:
    """Log-mean temperature difference [K or degC] of end differences dt1, dt2.

    (dt1 - dt2)/ln(dt1/dt2); equals dt1 when the two are equal.
    """
    if math.isclose(dt1, dt2, rel_tol=1e-9):
        return float(dt1)
    return float((dt1 - dt2) / math.log(dt1 / dt2))


def antoine_p(T: float, A: float, B: float, C: float) -> float:
    """Vapour pressure from log10(P) = A - B/(C + T).

    Units convention (classic tables): T in degC, P in mmHg. Constants given for other
    units (kPa, K, ln) must be used in those units. Returns P in the constants' units.
    """
    return float(10.0 ** (A - B / (C + T)))
