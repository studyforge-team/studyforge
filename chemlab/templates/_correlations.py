"""Textbook correlations as pure functions (numpy/scipy only, SI unless stated).

Not a template (no SPEC/run; the leading underscore keeps it out of discovery).
In the sandbox: `from chemlab._correlations import annular_fin_efficiency, ...`
"""

import functools
import math
from itertools import pairwise

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


def fuller_diffusivity(
    T: float, P: float, MA: float, MB: float, vA: float, vB: float
) -> float:
    """Binary gas diffusivity [m2/s], Fuller-Schettler-Giddings (Poling 5th ed. Eq. 11-4.4).

    T [K], P [Pa], MA, MB molar masses [g/mol], vA, vB summed diffusion volumes [cm3/mol]
    (Poling Table 11-1; chemlab._compounds FULLER_*). D [cm2/s] = 0.00143 T^1.75 /
    (P[bar] M_AB^0.5 (vA^(1/3) + vB^(1/3))^2) with M_AB = 2/(1/MA + 1/MB).
    """
    m_ab = 2.0 / (1.0 / MA + 1.0 / MB)
    d_cm2 = 0.00143 * T**1.75 / ((P / 1e5) * math.sqrt(m_ab) * (vA ** (1 / 3) + vB ** (1 / 3)) ** 2)
    return float(d_cm2 * 1e-4)


def wilke_chang_diffusivity(
    T: float, mu_B: float, MB: float, VA: float, phi: float = 2.6
) -> float:
    """Dilute solute A in liquid B, diffusivity [m2/s], Wilke-Chang (Poling Eq. 11-9.1).

    T [K], mu_B solvent viscosity [Pa s], MB solvent molar mass [g/mol], VA solute molar
    volume at its normal boiling point [cm3/mol], phi association factor (water 2.6,
    methanol 1.9, ethanol 1.5, unassociated 1.0). D [cm2/s] = 7.4e-8 (phi MB)^0.5 T /
    (mu_B[cP] VA^0.6).
    """
    d_cm2 = 7.4e-8 * math.sqrt(phi * MB) * T / (mu_B * 1e3 * VA**0.6)
    return float(d_cm2 * 1e-4)


def rayleigh_residue(F: float, xF: float, xW: float, alpha: float) -> float:
    """Residue W [same unit as F] after simple batch (Rayleigh) distillation, constant alpha.

    xF, xW light-key mole fractions in the charge and the final residue (xW < xF).
    ln(W/F) = [ln(xW/xF) + alpha ln((1-xF)/(1-xW))] / (alpha - 1)  (McCabe-Smith Eq. 21.x).
    The distillate is D = F - W with average composition (F xF - W xW)/D.
    """
    ln_wf = (math.log(xW / xF) + alpha * math.log((1 - xF) / (1 - xW))) / (alpha - 1)
    return float(F * math.exp(ln_wf))


def rachford_rice(z: list[float], K: list[float]) -> float:
    """Vapour fraction V/F [-] of an isothermal flash from feed z and K-values (Rachford-Rice).

    sum z_i (K_i - 1)/(1 + V (K_i - 1)) = 0 solved on (0, 1); returns 0.0 (all liquid) or
    1.0 (all vapour) outside the two-phase region. Then x_i = z_i/(1 + V (K_i - 1)), y_i = K_i x_i.
    """
    from scipy.optimize import brentq

    def g(v: float) -> float:
        return sum(zi * (k - 1) / (1 + v * (k - 1)) for zi, k in zip(z, K, strict=True))

    if g(0.0) <= 0:
        return 0.0
    if g(1.0) >= 0:
        return 1.0
    return float(brentq(g, 0.0, 1.0, xtol=1e-14))


def kremser_stages(y_in: float, y_out: float, x_in: float, m: float, A: float) -> float:
    """Theoretical stages [-] of a dilute counter-current absorber, Kremser equation.

    y_in, y_out gas mole fractions in and out, x_in entering liquid, m equilibrium slope
    (y* = m x), A = L/(m V) absorption factor (A != 1). N = ln[((y_in - m x_in)/(y_out -
    m x_in))(1 - 1/A) + 1/A] / ln A.
    """
    r = (y_in - m * x_in) / (y_out - m * x_in)
    return float(math.log(r * (1 - 1 / A) + 1 / A) / math.log(A))


# Lee-Kesler (1975) constants: simple fluid (0) and reference fluid n-octane (r).
_LK = {
    0: {"b": (0.1181193, 0.265728, 0.154790, 0.030323), "c": (0.0236744, 0.0186984, 0.0, 0.042724),
            "d": (0.155488e-4, 0.623689e-4), "beta": 0.65392, "gamma": 0.060167},
    1: {"b": (0.2026579, 0.331511, 0.027655, 0.203488), "c": (0.0313385, 0.0503618, 0.016901, 0.041577),
            "d": (0.48736e-4, 0.0740336e-4), "beta": 1.226, "gamma": 0.03754},
}
_LK_OMEGA_R = 0.3978


def _lk_fluid(Tr: float, Pr: float, k: dict, phase: str) -> dict:
    """Z, H^R/(R Tc), S^R/R, ln phi of one Lee-Kesler fluid (modified BWR in Vr = Pc V/(R Tc))."""
    from scipy.optimize import brentq

    b1, b2, b3, b4 = k["b"]
    c1, c2, c3, c4 = k["c"]
    d1, d2 = k["d"]
    be, ga = k["beta"], k["gamma"]
    B = b1 - b2 / Tr - b3 / Tr**2 - b4 / Tr**3
    C = c1 - c2 / Tr + c3 / Tr**3
    D = d1 + d2 / Tr

    def z_of(v: float) -> float:
        return 1 + B / v + C / v**2 + D / v**5 + c4 / (Tr**3 * v**2) * (be + ga / v**2) * math.exp(-ga / v**2)

    def f(v: float) -> float:
        return Pr * v / Tr - z_of(v)

    # scan a log grid from dilute gas (Vr large) down to the dense limit, bracket sign changes
    grid = [Tr / Pr * 10 ** (1.5 - 0.02 * i) for i in range(200)]
    grid = [v for v in grid if v > 0.05]
    roots = [brentq(f, hi, lo, xtol=1e-14) for hi, lo in pairwise(grid) if f(hi) * f(lo) < 0]
    if not roots:
        raise ValueError("no Lee-Kesler volume root found")
    v = roots[0] if phase == "vapour" else roots[-1]
    z = Pr * v / Tr
    e = c4 / (2 * Tr**3 * ga) * (be + 1 - (be + 1 + ga / v**2) * math.exp(-ga / v**2))
    hr = Tr * (z - 1 - (b2 + 2 * b3 / Tr + 3 * b4 / Tr**2) / (Tr * v)
               - (c2 - 3 * c3 / Tr**2) / (2 * Tr * v**2) + d2 / (5 * Tr * v**5) + 3 * e)
    sr = (math.log(z) - (b1 + b3 / Tr**2 + 2 * b4 / Tr**3) / v - (c1 - 2 * c3 / Tr**3) / (2 * v**2)
          - d1 / (5 * v**5) + 2 * e)
    lnphi = z - 1 - math.log(z) + B / v + C / (2 * v**2) + D / (5 * v**5) + e
    return {"Z": z, "HR": hr, "SR": sr, "lnphi": lnphi}


class Props(dict):
    """A result dict that also reads as r.Z and unpacks to its main values in order, so
    r["Z"], r.Z and `Z, HR_RTc, SR_R, lnphi = lee_kesler(...)` all work (models write all three)."""

    def __init__(self, main: tuple[str, ...], values: dict) -> None:
        super().__init__(values)
        self._main = main

    def __iter__(self):  # type: ignore[override]
        return iter([self[k] for k in self._main])

    def __getattr__(self, k: str) -> float:
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None


_MAIN = ("Z", "HR_RTc", "SR_R", "lnphi")


def lee_kesler(Tr: float, Pr: float, omega: float, phase: str = "vapour") -> Props:
    """Lee-Kesler (AIChE J. 21, 1975, 510) residual properties; SVNA ch. 3 and 6, Tables E.1-E.12.

    Tr, Pr reduced T and P [-], omega acentric factor. phase "vapour" takes the largest volume
    root, "liquid" the smallest (only distinct below the critical point). Returns Z, Z0, Z1,
    HR_RTc = H^R/(R Tc) [-], SR_R = S^R/R [-], lnphi, and the parts HR0_RTc, HR1_RTc, SR0_R,
    SR1_R (X = X0 + omega X1, X1 = (X_ref - X0)/omega_ref, omega_ref = 0.3978).
    """
    s = _lk_fluid(Tr, Pr, _LK[0], phase)
    r = _lk_fluid(Tr, Pr, _LK[1], phase)
    p = {n: (r[n] - s[n]) / _LK_OMEGA_R for n in s}
    return Props(_MAIN, {
        "Z": s["Z"] + omega * p["Z"], "Z0": s["Z"], "Z1": p["Z"],
        "HR_RTc": s["HR"] + omega * p["HR"], "HR0_RTc": s["HR"], "HR1_RTc": p["HR"],
        "SR_R": s["SR"] + omega * p["SR"], "SR0_R": s["SR"], "SR1_R": p["SR"],
        "lnphi": s["lnphi"] + omega * p["lnphi"],
    })


def pitzer_virial(Tr: float, Pr: float, omega: float) -> Props:
    """Pitzer second-virial correlation, valid at low Pr (SVNA eqs 3.57-3.66, 6.89-6.90).

    Z = 1 + (B0 + omega B1) Pr/Tr with B0 = 0.083 - 0.422/Tr^1.6, B1 = 0.139 - 0.172/Tr^4.2.
    Returns Z, HR_RTc = H^R/(R Tc), SR_R = S^R/R and lnphi (all [-]).
    """
    b0, b1 = 0.083 - 0.422 / Tr**1.6, 0.139 - 0.172 / Tr**4.2
    db0, db1 = 0.6752 / Tr**2.6, 0.7224 / Tr**5.2  # exact dB/dTr (SVNA rounds to 0.675, 0.722)
    bhat = b0 + omega * b1
    return Props(_MAIN, {
        "Z": 1 + bhat * Pr / Tr,
        "HR_RTc": Pr * (bhat - Tr * (db0 + omega * db1)),
        "SR_R": -Pr * (db0 + omega * db1),
        "lnphi": bhat * Pr / Tr,
    })


def ig_cp_integrals(T0: float, T: float, A: float, B: float, C: float = 0.0, D: float = 0.0) -> Props:
    """Ideal-gas sensible heat from T0 to T [K] for Cp/R = A + B T + C T^2 + D T^-2 (SVNA ICPH/ICPS).

    Returns dH_R = integral Cp/R dT [K] and dS_R = integral (Cp/R)/T dT [-].
    """
    dh = A * (T - T0) + B / 2 * (T**2 - T0**2) + C / 3 * (T**3 - T0**3) + D * (1 / T0 - 1 / T)
    ds = A * math.log(T / T0) + B * (T - T0) + C / 2 * (T**2 - T0**2) + D / 2 * (1 / T0**2 - 1 / T**2)
    return Props(("dH_R", "dS_R"), {"dH_R": dh, "dS_R": ds})


def gamma_binary(model: str, x1: float, p: tuple, T: float | None = None) -> Props:
    """Liquid activity coefficients gamma1, gamma2 [-] of a binary (SVNA ch. 12-13).

    model "margules" p = (A12, A21): ln g1 = x2^2 [A12 + 2 (A21 - A12) x1] (two-parameter);
    "van_laar" p = (A12', A21'): ln g1 = A12' / (1 + A12' x1/(A21' x2))^2;
    "wilson" p = (L12, L21) (SVNA eqs 13.45-13.46): ln g1 = -ln(x1 + L12 x2) + x2 [L12/(x1 + L12 x2)
    - L21/(x2 + L21 x1)]; "nrtl" p = (tau12, tau21, alpha), G = exp(-alpha tau).
    x1 mole fraction of component 1. T is accepted for call symmetry and unused: supply
    temperature-dependent parameters (tau, Lambda) already evaluated at T.
    """
    x2 = 1.0 - x1
    if model == "margules":
        a12, a21 = p
        l1 = x2**2 * (a12 + 2 * (a21 - a12) * x1)
        l2 = x1**2 * (a21 + 2 * (a12 - a21) * x2)
    elif model == "van_laar":
        a12, a21 = p
        d = (a12 * x1 + a21 * x2) ** 2
        l1 = a12 * (a21 * x2) ** 2 / d
        l2 = a21 * (a12 * x1) ** 2 / d
    elif model == "wilson":
        l12, l21 = p
        s1, s2 = x1 + l12 * x2, x2 + l21 * x1
        c = l12 / s1 - l21 / s2
        l1 = -math.log(s1) + x2 * c
        l2 = -math.log(s2) - x1 * c
    elif model == "nrtl":
        t12, t21, alpha = p
        g12, g21 = math.exp(-alpha * t12), math.exp(-alpha * t21)
        l1 = x2**2 * (t21 * (g21 / (x1 + x2 * g21)) ** 2 + t12 * g12 / (x2 + x1 * g12) ** 2)
        l2 = x1**2 * (t12 * (g12 / (x2 + x1 * g12)) ** 2 + t21 * g21 / (x1 + x2 * g21) ** 2)
    else:
        raise ValueError(f"unknown activity model {model!r}")
    return Props(("gamma1", "gamma2"), {"gamma1": math.exp(l1), "gamma2": math.exp(l2)})


# SVNA Table 3.1: sigma, epsilon, Omega, Psi (alpha(Tr, omega) in _cubic_alpha)
_CUBIC = {
    "vdW": (0.0, 0.0, 1 / 8, 27 / 64),
    "RK": (1.0, 0.0, 0.08664, 0.42748),
    "SRK": (1.0, 0.0, 0.08664, 0.42748),
    "PR": (1 + math.sqrt(2), 1 - math.sqrt(2), 0.07779, 0.45724),
}
_R = 8.314


def _cubic_alpha(eos: str, Tr: float, omega: float) -> float:
    if eos == "vdW":
        return 1.0
    if eos == "RK":
        return Tr**-0.5
    k = 0.480 + 1.574 * omega - 0.176 * omega**2 if eos == "SRK" else 0.37464 + 1.54226 * omega - 0.26992 * omega**2
    return (1 + k * (1 - math.sqrt(Tr))) ** 2


def _cubic_roots(T: float, P: float, Tc: float, Pc: float, omega: float, eos: str):
    """(roots Z > B ascending, beta, q, sigma, epsilon) of the SVNA generic cubic."""
    import numpy as np

    if eos not in _CUBIC:
        raise ValueError(f"unknown equation of state {eos!r}")
    sig, eps, om, psi = _CUBIC[eos]
    Tr, Pr = T / Tc, P / Pc
    beta = om * Pr / Tr
    q = psi * _cubic_alpha(eos, Tr, omega) / (om * Tr)
    poly = np.polymul([1.0, -(1 + beta)], [1.0, (eps + sig) * beta, eps * sig * beta**2])
    poly = np.polyadd(poly, [q * beta, -q * beta**2])
    zs = sorted(float(z.real) for z in np.roots(poly) if abs(z.imag) < 1e-9 * max(1.0, abs(z.real)) and z.real > beta)
    return zs, beta, q, sig, eps


def _cubic_lnphi(z: float, beta: float, q: float, sig: float, eps: float) -> float:
    i = beta / z if sig == eps else math.log((z + sig * beta) / (z + eps * beta)) / (sig - eps)
    return z - 1 - math.log(z - beta) - q * i


def cubic_eos(T: float, P: float, Tc: float, Pc: float, omega: float = 0.0, eos: str = "PR") -> Props:
    """Generic cubic equation of state (SVNA ch. 3 Table 3.1, eqs 3.52-3.53, 13.68).

    eos "vdW", "RK", "SRK" or "PR"; T, Tc [K]; P and Pc in the SAME pressure unit (Z and ln phi
    are unit-free; the molar volumes need Pa because R = 8.314 J/mol/K, so pass Pa for V in m3/mol).
    Real roots Z > B are kept: Z_vap is the largest, Z_liq the smallest (equal with one root).
    ln phi = Z - 1 - ln(Z - beta) - q I, I = ln[(Z + sigma beta)/(Z + eps beta)]/(sigma - eps).
    Returns Z_vap, Z_liq, lnphi_vap, lnphi_liq, plus V_vap, V_liq [m3/mol], A = q beta, B = beta.
    """
    zs, beta, q, sig, eps = _cubic_roots(T, P, Tc, Pc, omega, eos)
    if not zs:
        raise ValueError("no physical cubic root found")
    zv, zl = zs[-1], zs[0]
    return Props(("Z_vap", "Z_liq", "lnphi_vap", "lnphi_liq"), {
        "Z_vap": zv, "Z_liq": zl,
        "lnphi_vap": _cubic_lnphi(zv, beta, q, sig, eps), "lnphi_liq": _cubic_lnphi(zl, beta, q, sig, eps),
        "V_vap": zv * _R * T / P, "V_liq": zl * _R * T / P, "A": q * beta, "B": beta,
    })


def cubic_psat(T: float, Tc: float, Pc: float, omega: float = 0.0, eos: str = "PR") -> Props:
    """Vapour pressure from a cubic EOS: ln phi_vap = ln phi_liq (SVNA ch. 14).

    T, Tc [K], Pc [Pa] -> Psat [Pa] (also Z_vap, Z_liq, V_vap, V_liq [m3/mol]). Scans ln P below Pc
    for the three-root region, picks the sign change of the fugacity difference nearest the
    Lee-Kesler/Wilson estimate Pc 10^(7/3 (1 + omega)(1 - Tc/T)) and solves it with brentq.
    ValueError at or above Tc.
    """
    from scipy.optimize import brentq

    if T >= Tc:
        raise ValueError("T must be below Tc")

    def diff(lnp: float) -> float | None:
        zs, beta, q, sig, eps = _cubic_roots(T, math.exp(lnp), Tc, Pc, omega, eos)
        if len(zs) < 2 or zs[-1] - zs[0] < 1e-8:
            return None
        return _cubic_lnphi(zs[-1], beta, q, sig, eps) - _cubic_lnphi(zs[0], beta, q, sig, eps)

    guess = math.log(Pc) + 7 / 3 * (1 + omega) * (1 - Tc / T) * math.log(10)
    grid = [math.log(Pc) + math.log(1e-5) * (1 - i / 600) for i in range(601)]
    vals = [(g, diff(g)) for g in grid]
    brackets = [(a, b) for (a, fa), (b, fb) in pairwise(vals) if fa is not None and fb is not None and fa * fb < 0]
    if not brackets:
        raise ValueError("no vapour-liquid root bracket found")
    a, b = min(brackets, key=lambda ab: abs((ab[0] + ab[1]) / 2 - guess))
    lnp = brentq(lambda v: diff(v), a, b, xtol=1e-14)
    psat = math.exp(lnp)
    r = cubic_eos(T, psat, Tc, Pc, omega, eos)
    return Props(("Psat", "Z_vap", "Z_liq"), {
        "Psat": psat, "Z_vap": r["Z_vap"], "Z_liq": r["Z_liq"], "V_vap": r["V_vap"], "V_liq": r["V_liq"],
    })


def _bracket_T(f, T0: float):
    """Bracket the root of an increasing f(T), expanding from T0 with growing steps."""
    f0, step = f(T0), 5.0
    lo = hi = T0
    for _ in range(80):
        if f0 < 0:
            hi += step
            if f(hi) >= 0:
                return lo, hi
            lo = hi
        else:
            lo -= step
            if f(lo) <= 0:
                return lo, hi
            hi = lo
        step *= 1.4
    raise ValueError("could not bracket the temperature")


def _gam(gamma, x, T) -> list[float]:
    return [1.0] * len(x) if gamma is None else list(gamma(x, T))


def bubble_t(x: list[float], P: float, psat: list, gamma=None, T0: float | None = None) -> Props:
    """Bubble-point temperature of liquid x at P (modified Raoult's law, SVNA ch. 10 and 13).

    psat list of callables Psat_i(T) in the unit of P (and T); gamma optional callable
    gamma(x, T) -> list of activity coefficients. Solves sum x_i gamma_i Psat_i = P with brentq
    on T, bracketed by expansion from T0 (default 300, so give T0 if T is not in kelvin).
    Returns T and vapour composition y_i = x_i gamma_i Psat_i / P.
    """
    from scipy.optimize import brentq

    def f(t: float) -> float:
        return sum(xi * g * p(t) for xi, g, p in zip(x, _gam(gamma, x, t), psat, strict=True)) - P

    lo, hi = _bracket_T(f, 300.0 if T0 is None else T0)
    t = float(brentq(f, lo, hi, xtol=1e-12))
    y = [xi * g * p(t) / P for xi, g, p in zip(x, _gam(gamma, x, t), psat, strict=True)]
    return Props(("T", "y"), {"T": t, "y": y})


def dew_t(y: list[float], P: float, psat: list, gamma=None, T0: float | None = None) -> Props:
    """Dew-point temperature of vapour y at P (modified Raoult's law); see bubble_t.

    Solves sum y_i P/(gamma_i Psat_i) = 1; with gamma the liquid x is iterated (x_i = y_i P/(gamma_i
    Psat_i), normalised) to convergence. Returns T and liquid composition x.
    """
    from scipy.optimize import brentq

    x = list(y)
    t = 300.0 if T0 is None else T0
    for _ in range(200 if gamma else 1):

        def f(tt: float, xc: list[float] = x) -> float:  # increasing in T
            return 1.0 - P * sum(yi / (g * p(tt)) for yi, g, p in zip(y, _gam(gamma, xc, tt), psat, strict=True))

        lo, hi = _bracket_T(f, t)
        t = float(brentq(f, lo, hi, xtol=1e-12))
        new = [yi * P / (g * p(t)) for yi, g, p in zip(y, _gam(gamma, x, t), psat, strict=True)]
        s = sum(new)
        new = [v / s for v in new]
        done = max(abs(a - b) for a, b in zip(new, x, strict=True)) < 1e-12
        x = new
        if done:
            break
    return Props(("T", "x"), {"T": t, "x": x})


def _gam_x(gammas, x: list[float]) -> list[float]:
    if gammas is None:
        return [1.0] * len(x)
    return list(gammas(x)) if callable(gammas) else list(gammas)


def bubble_p(x: list[float], psat_values: list[float], gammas=None) -> Props:
    """Bubble pressure P = sum x_i gamma_i Psat_i and vapour y_i = x_i gamma_i Psat_i / P.

    gammas: list of activity coefficients, or callable gamma(x) -> list; default ideal (1).
    """
    g = _gam_x(gammas, x)
    terms = [xi * gi * p for xi, gi, p in zip(x, g, psat_values, strict=True)]
    p_tot = sum(terms)
    return Props(("P", "y"), {"P": p_tot, "y": [t / p_tot for t in terms]})


def dew_p(y: list[float], psat_values: list[float], gammas=None) -> Props:
    """Dew pressure P = 1/sum(y_i/(gamma_i Psat_i)) and liquid x_i = y_i P/(gamma_i Psat_i).

    gammas: list (closed form) or callable gamma(x) -> list (x iterated to convergence).
    """
    x = list(y)
    for _ in range(200 if callable(gammas) else 1):
        g = _gam_x(gammas, x)
        p_tot = 1.0 / sum(yi / (gi * p) for yi, gi, p in zip(y, g, psat_values, strict=True))
        new = [yi * p_tot / (gi * p) for yi, gi, p in zip(y, g, psat_values, strict=True)]
        s = sum(new)
        new = [v / s for v in new]
        done = max(abs(a - b) for a, b in zip(new, x, strict=True)) < 1e-12
        x = new
        if done:
            break
    return Props(("P", "x"), {"P": p_tot, "x": x})


def _scalar_args(fn):
    """fsolve and friends pass one-element arrays into the model's own functions, which then call
    these tools: take such an argument as the number it holds (math.exp(array) would fail)."""

    def one(a):
        return a.reshape(()).item() if getattr(a, "ndim", 0) and getattr(a, "size", 0) == 1 else a

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*map(one, args), **{k: one(v) for k, v in kwargs.items()})

    return wrapper


for _name, _fn in list(globals().items()):
    if not _name.startswith("_") and callable(_fn) and not isinstance(_fn, type) and getattr(_fn, "__module__", None) == __name__:
        globals()[_name] = _scalar_args(_fn)
del _name, _fn
