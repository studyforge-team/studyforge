"""Recompute every P1 golden proposal two independent ways and check the JSON files.

    python docs/golden-proposals/verify_p1_problems.py          # verify (CI-style)
    python docs/golden-proposals/verify_p1_problems.py --write  # regenerate JSON + md

Needs numpy, scipy and the editable `chemlab` install. No sympy.
Part 1: 10 calculation problems, method 1 vs method 2 within 1e-6 relative, then
vs p1_problems.json (6 significant digits stored, compared at 1e-5).
Part 2: ChemLab cases: independent calculation vs the template within 1%.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq, fsolve

HERE = Path(__file__).parent
R_GAS = 8.314462618


def rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


# ----------------------------------------------------------------- problems
# Each entry: (id, topic, difficulty, question, unit, method_1 fn, method_2 fn,
#              m1 text, m2 text)

def p01():
    k = 0.045
    m1 = math.log(1 / (1 - 0.9)) / k
    ev = lambda t, y: y[0] - 0.1  # CA/CA0 reaches 0.1
    ev.terminal = True
    s = solve_ivp(lambda t, y: -k * y, (0, 500), [1.0], events=ev, rtol=1e-12, atol=1e-14)
    return m1, float(s.t_events[0][0])


def p02():
    m1 = 4.2e5 * 0.50 / (R_GAS * 350.0)  # SI: Pa, m^3
    m2 = 4.2 * 500.0 / (0.08314462618 * 350.0)  # bar, litres
    return m1, m2


def p03():
    mu, rho, Q, L, D = 0.08, 880.0, 2.0e-3, 50.0, 0.05
    assert 4 * rho * Q / (math.pi * D * mu) < 2100
    m1 = 128 * mu * L * Q / (math.pi * D**4)  # Hagen-Poiseuille
    v = Q / (math.pi * D**2 / 4)
    f = 64 / (rho * v * D / mu)  # Darcy f = 64/Re
    m2 = f * (L / D) * rho * v**2 / 2
    return m1 / 1e3, m2 / 1e3  # kPa


def p04():
    L = np.array([0.23, 0.12, 0.010])
    k = np.array([1.1, 0.15, 45.0])
    Ti, To = 1100.0, 90.0
    m1 = (Ti - To) / np.sum(L / k)
    # method 2: unknown interface temperatures from a linear system, flux from layer 1
    # T1,T2 = interface temps; (Ti-T1)k0/L0 = (T1-T2)k1/L1 = (T2-To)k2/L2
    c = k / L
    A = np.array([[c[0] + c[1], -c[1]], [-c[1], c[1] + c[2]]])
    b = np.array([c[0] * Ti, c[2] * To])
    T1, T2 = np.linalg.solve(A, b)
    m2 = c[0] * (Ti - T1)
    assert rel(m2, c[2] * (T2 - To)) < 1e-9
    return float(m1), float(m2)


def p05():
    mh, cph, Th1, Th2 = 2.0, 2.1, 160.0, 100.0
    mc, cpc, Tc1 = 2.5, 4.18, 20.0
    U = 350.0
    Q = mh * cph * (Th1 - Th2) * 1e3  # W
    Tc2 = Tc1 + Q / (mc * cpc * 1e3)
    d1, d2 = Th1 - Tc2, Th2 - Tc1
    m1 = Q / (U * (d1 - d2) / math.log(d1 / d2))
    Ch, Cc = mh * cph * 1e3, mc * cpc * 1e3
    Cmin, Cmax = min(Ch, Cc), max(Ch, Cc)
    eps = Q / (Cmin * (Th1 - Tc1))
    Cr = Cmin / Cmax
    ntu = math.log((eps - 1) / (eps * Cr - 1)) / (Cr - 1)
    m2 = ntu * Cmin / U
    return m1, m2


def p06():
    g, Rg, T1, P1, P2 = 1.4, 0.287, 300.0, 100.0, 600.0  # kPa, kJ/(kg K)
    m1 = g / (g - 1) * Rg * T1 * ((P2 / P1) ** ((g - 1) / g) - 1)
    v = lambda P: Rg * T1 / P1 * (P1 / P) ** (1 / g)  # m^3/kg, P V^g = const
    m2 = quad(v, P1, P2, epsabs=1e-12, epsrel=1e-13)[0]  # integral v dP, kJ/kg
    return m1, m2


def p07():
    z = np.array([0.30, 0.40, 0.30])
    K = np.array([3.2, 1.1, 0.25])
    c = K - 1
    rr = lambda psi: np.sum(z * c / (1 + psi * c))
    m1 = brentq(rr, 0.0, 1.0, xtol=1e-12)
    # method 2: clear denominators -> polynomial in psi, take the root in [0, 1]
    poly = np.polynomial.Polynomial([0.0])
    for i in range(3):
        term = np.polynomial.Polynomial([z[i] * c[i]])
        for j in range(3):
            if j != i:
                term = term * np.polynomial.Polynomial([1.0, c[j]])
        poly = poly + term
    roots = [r.real for r in poly.roots() if abs(r.imag) < 1e-12 and 0 <= r.real <= 1]
    assert len(roots) == 1
    return float(m1), float(roots[0])


def p08():
    k, v0, V = 0.12, 20.0, 150.0  # min^-1, L/min, L
    tau = V / v0
    m1 = 100 * (1 - 1 / (1 + k * tau) ** 2)
    # method 2: solve both steady balances simultaneously (CA0 = 1)
    f = lambda c: [1 - c[0] - k * tau * c[0], c[0] - c[1] - k * tau * c[1]]
    c = fsolve(f, [0.5, 0.2], xtol=1e-12)
    return m1, 100 * (1 - c[1])


def p09():
    a, b, y0, t = 0.8, 0.05, 2.0, 3.0
    # Bernoulli: u = y^-2, u' = -2a u + 2b, u -> b/a
    ue = b / a
    u = ue + (y0**-2 - ue) * math.exp(-2 * a * t)
    m1 = u**-0.5
    s = solve_ivp(lambda t, y: a * y - b * y**3, (0, t), [y0], method="DOP853",
                  rtol=1e-13, atol=1e-14)
    return m1, float(s.y[0, -1])


def p10():
    Bi = 2.5
    m1 = brentq(lambda x: x * math.tan(x) - Bi, 0.1, math.pi / 2 - 1e-9, xtol=1e-15)
    x = 1.0  # method 2: Newton on x sin x - Bi cos x (no pole)
    for _ in range(50):
        f = x * math.sin(x) - Bi * math.cos(x)
        fp = math.sin(x) + x * math.cos(x) + Bi * math.sin(x)
        x -= f / fp
    return m1, x


PROBLEMS = [
    ("P1-01", "CRE: batch reactor, first order", "easy",
     "A first-order liquid-phase reaction A -> B runs in a well-mixed batch reactor with k = 0.045 min^-1. How long does it take to reach 90% conversion of A? Give the answer in minutes.",
     "min", p01, "t = ln(1/(1-X))/k", "solve_ivp dCA/dt = -k CA with a stop event at CA/CA0 = 0.1"),
    ("P1-02", "Thermodynamics: ideal gas", "easy",
     "A 0.50 m^3 tank holds nitrogen at 350 K and 4.2 bar absolute. Treating it as an ideal gas, how many moles of nitrogen are in the tank?",
     "mol", p02, "n = PV/(RT) in SI (Pa, m^3, J/mol/K)", "n = PV/(RT) in bar, litres, R = 0.0831446 L bar/(mol K)"),
    ("P1-03", "Fluid flow: laminar pipe", "easy",
     "Oil (viscosity 0.080 Pa s, density 880 kg/m^3) flows at 2.0 L/s through a 50 m long horizontal pipe of 0.050 m inside diameter. What is the pressure drop in kPa?",
     "kPa", p03, "Hagen-Poiseuille dP = 128 mu L Q/(pi D^4); Re = 560 so laminar", "Darcy-Weisbach with f = 64/Re"),
    ("P1-04", "Heat transfer: composite wall", "easy",
     "A furnace wall has 0.23 m of firebrick (k = 1.1 W/(m K)), 0.12 m of insulating brick (k = 0.15 W/(m K)) and a 10 mm steel plate (k = 45 W/(m K)). The hot face is at 1100 C and the outer steel surface is at 90 C. What is the heat loss per square metre of wall in W/m^2?",
     "W/m^2", p04, "q = dT / sum(L/k)", "solve the two interface temperatures as a linear system, then q = k dT/L in layer 1"),
    ("P1-05", "Heat transfer: counter-current exchanger", "medium",
     "Hot oil (2.0 kg/s, cp = 2.1 kJ/(kg K)) is cooled from 160 C to 100 C in a counter-current heat exchanger by water (2.5 kg/s, cp = 4.18 kJ/(kg K)) entering at 20 C. U = 350 W/(m^2 K). What heat transfer area is needed, in m^2?",
     "m^2", p05, "Q = U A LMTD (counter-current)", "effectiveness-NTU, counter-flow formula, A = NTU Cmin/U"),
    ("P1-06", "Thermodynamics: isentropic compression", "medium",
     "Air (ideal gas, R = 0.287 kJ/(kg K), gamma = 1.4) enters a reversible adiabatic compressor at 100 kPa and 300 K and leaves at 600 kPa. What is the shaft work per kg of air in kJ/kg?",
     "kJ/kg", p06, "w = gamma/(gamma-1) R T1 [(P2/P1)^((gamma-1)/gamma) - 1]", "numerical integral of v dP along P v^gamma = const"),
    ("P1-07", "Separations: flash", "medium",
     "A liquid feed with mole fractions 0.30 (A), 0.40 (B) and 0.30 (C) is flashed isothermally. The K-values at flash conditions are K_A = 3.2, K_B = 1.1, K_C = 0.25. What fraction of the feed leaves as vapour (V/F)?",
     "-", p07, "Rachford-Rice equation solved with brentq on [0, 1]", "Rachford-Rice cleared of denominators, polynomial roots, root in [0, 1]"),
    ("P1-08", "CRE: CSTRs in series", "medium",
     "Two equal CSTRs of 150 L each are in series. A first-order reaction A -> B with k = 0.12 min^-1 occurs in liquid fed at 20 L/min. What is the overall conversion of A leaving the second reactor, in percent?",
     "%", p08, "X = 1 - 1/(1 + k tau)^2 with tau = 7.5 min", "simultaneous steady-state mole balances solved with fsolve"),
    ("P1-09", "Maths: nonlinear ODE initial value problem", "hard",
     "Solve dy/dt = 0.8 y - 0.05 y^3 with y(0) = 2. What is y(3)?",
     "-", p09, "Bernoulli substitution u = y^-2 gives a linear ODE with a closed form", "scipy solve_ivp, DOP853, rtol 1e-13"),
    ("P1-10", "Maths: root of a nonlinear equation", "hard",
     "Find the smallest positive root of x tan(x) = 2.5, with x in radians (the first eigenvalue for a slab with Biot number 2.5).",
     "rad", p10, "brentq on x tan x - 2.5 over (0.1, pi/2)", "Newton iteration on x sin x - 2.5 cos x (no pole)"),
]


def sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n - 1}e}")


def build_problems():
    out = []
    for pid, topic, diff, q, unit, fn, t1, t2 in PROBLEMS:
        a, b = fn()
        assert rel(a, b) < 1e-6, (pid, a, b)
        out.append({
            "id": pid, "question": q, "answer": {"value": sig(a), "unit": unit},
            "tolerance_rel": 0.01, "method_1": t1, "method_2": t2,
            "topic": topic, "difficulty": diff,
            "source_note": "standard textbook form; numbers original",
            "_raw": (a, b),
        })
    return out


# ------------------------------------------------------------ chemlab cases
def mccabe_independent(F, zF, xD, xB, q, a, R):
    """Own implementation: Underwood Rmin, balances, top-down stepping."""
    eq_inv = lambda y: y / (a - (a - 1) * y)
    # Underwood (binary, constant alpha): find theta in (1, a) with
    #   a zF/(a - th) + (1 - zF)/(1 - th) = 1 - q ; Rmin + 1 = a xD/(a - th) + (1-xD)/(1-th)
    g = lambda th: a * zF / (a - th) + (1 - zF) / (1 - th) - (1 - q)
    th = brentq(g, 1 + 1e-9, a - 1e-9, xtol=1e-15)
    rmin = a * xD / (a - th) + (1 - xD) / (1 - th) - 1
    assert R > rmin
    D = F * (zF - xB) / (xD - xB)
    L = R * D
    V = L + D
    Lb = L + q * F
    Vb = V - (1 - q) * F
    # operating lines: rectifying y = L/V x + D xD/V; stripping y = Lb/Vb x - B xB/Vb
    B = F - D
    rect = lambda x: L / V * x + D * xD / V
    strip = lambda x: Lb / Vb * x - B * xB / Vb
    # intersection of the two operating lines
    xi = (D * xD / V + B * xB / Vb) / (Lb / Vb - L / V)
    y, n, feed, xprev = xD, 0, 0, xD
    while True:
        n += 1
        x = eq_inv(y)
        if not feed and x <= xi:
            feed = n
        if x <= xB:
            break
        xprev = x
        y = strip(x) if feed else rect(x)
        assert n < 200
    nfrac = (n - 1) + (xprev - xB) / (xprev - x)
    return dict(Rmin=rmin, D=D, B=B, V=V, V_bar=Vb, N_theoretical=n, feed_stage=feed,
                N_fractional=nfrac), (x, xB)


def chemlab_cases():
    cases = []
    # CSTR isothermal, n = 2: closed-form quadratic
    p = dict(CA0=1500.0, v0=0.02, V=3.0, n=2.0, k0=50.0, Ea=4.0e4, T0=320.0, isothermal=1.0)
    k = p["k0"] * math.exp(-p["Ea"] / (R_GAS * p["T0"]))
    tau = p["V"] / p["v0"]
    Da = k * tau * p["CA0"]
    X = (2 * Da + 1 - math.sqrt(4 * Da + 1)) / (2 * Da)
    # cross-check with a separate numeric method: relax dCA/dt to steady state
    s = solve_ivp(lambda t, c: [(p["CA0"] - c[0]) / tau - k * c[0] ** 2], (0, 40 * tau),
                  [p["CA0"]], method="LSODA", rtol=1e-12, atol=1e-12)
    assert rel(1 - s.y[0, -1] / p["CA0"], X) < 1e-6
    cases.append(dict(id="CSTR-1", template="cstr", inputs=p,
        expected={"X": [X, "-"], "CA": [p["CA0"] * (1 - X), "mol/m^3"], "tau": [tau, "s"], "Da": [Da, "-"]},
        n_steady_states=1,
        independent="Isothermal 2nd-order CSTR: X = (2Da+1-sqrt(4Da+1))/(2Da), Da = k tau CA0; checked by integrating dCA/dt to steady state with LSODA."))

    # CSTR adiabatic, 3 steady states: roots in T-space of first-order energy balance
    p = dict(CA0=2000.0, v0=0.01, V=1.0, n=1.0, k0=1.0e10, Ea=8.0e4, dHr=-2.0e5,
             rho_cp=4.18e6, UA=0.0, Ta=300.0, T0=300.0, isothermal=0.0)
    tau = p["V"] / p["v0"]
    dT = -p["dHr"] * p["CA0"] / p["rho_cp"]
    def resid(T):
        Da = p["k0"] * math.exp(-p["Ea"] / (R_GAS * T)) * tau
        return dT * Da / (1 + Da) - (T - p["T0"])
    Ts = np.linspace(p["T0"] + 1e-6, p["T0"] + dT, 40001)
    v = [resid(t) for t in Ts]
    roots = [brentq(resid, Ts[i], Ts[i + 1], xtol=1e-12) for i in range(len(Ts) - 1) if v[i] * v[i + 1] < 0]
    assert len(roots) == 3
    Xs = [(r - p["T0"]) / dT for r in roots]
    # stability by dynamic check: slope of G - R (negative = stable)
    h = 1e-4
    stable = [resid(r + h) < resid(r - h) for r in roots]
    assert stable == [True, False, True]
    cases.append(dict(id="CSTR-2", template="cstr", inputs=p,
        expected={"T": [roots[0], "K"], "X": [Xs[0], "-"]},
        n_steady_states=3,
        steady_states=[{"T": r, "X": x, "stable": st} for r, x, st in zip(roots, Xs, stable)],
        independent="First order, adiabatic: X = Da/(1+Da) and T = T0 + dT_ad X, so roots of dT_ad Da(T)/(1+Da(T)) - (T - T0) in T, scanned on a grid and refined with brentq. Stability from the sign of d(G-R)/dT. Outputs are the lowest-T stable state."))

    # PFR first order and second order: separate numeric integration in volume
    def pfr_case(cid, n, k, CA0, v0, V, text):
        p = dict(CA0=CA0, v0=v0, V=V, D=0.1, n=float(n), k=k)
        s = solve_ivp(lambda z, c: [-k * max(c[0], 0.0) ** n / v0], (0, V), [CA0],
                      method="DOP853", rtol=1e-12, atol=1e-12)
        ca = float(s.y[0, -1])
        return dict(id=cid, template="pfr", inputs=p,
            expected={"X": [1 - ca / CA0, "-"], "CA": [ca, "mol/m^3"], "tau": [V / v0, "s"],
                      "length_m": [4 * V / (math.pi * 0.1**2), "m"]},
            independent=text)
    c1 = pfr_case("PFR-1", 1, 0.012, 800.0, 0.002, 0.5, "First order: integrate v0 dCA/dV = -k CA with DOP853; cross-checked against X = 1 - exp(-k tau).")
    assert rel(c1["expected"]["X"][0], 1 - math.exp(-0.012 * 250)) < 1e-8
    c2 = pfr_case("PFR-2", 2, 1.0e-5, 1200.0, 0.002, 0.8, "Second order: integrate v0 dCA/dV = -k CA^2 with DOP853; cross-checked against X = Da/(1+Da), Da = k tau CA0.")
    Da2 = 1e-5 * 400 * 1200
    assert rel(c2["expected"]["X"][0], Da2 / (1 + Da2)) < 1e-8
    cases += [c1, c2]

    # batch: time to X_target by event integration + closed form
    def batch_case(cid, n, k, CA0, X_t, t, text, closed):
        p = dict(CA0=CA0, V=0.5, n=float(n), k=k, t=t, X_target=X_t)
        ev = lambda tt, c: c[0] - CA0 * (1 - X_t)
        ev.terminal = True
        s = solve_ivp(lambda tt, c: [-k * max(c[0], 0.0) ** n], (0, 1e6), [CA0],
                      method="DOP853", events=ev, rtol=1e-12, atol=1e-12)
        tt = float(s.t_events[0][0])
        assert rel(tt, closed) < 1e-6, (tt, closed)
        s2 = solve_ivp(lambda u, c: [-k * max(c[0], 0.0) ** n], (0, t), [CA0],
                       method="DOP853", rtol=1e-12, atol=1e-12)
        Xt = 1 - float(s2.y[0, -1]) / CA0
        return dict(id=cid, template="batch", inputs=p,
            expected={"t_for_target": [tt, "s"], "X": [Xt, "-"]}, independent=text)
    cases.append(batch_case("BATCH-1", 1, 0.004, 1000.0, 0.95, 300.0,
        "First order: t = ln(1/(1-X))/k = 748.9 s; X(t) from DOP853; t_target also found by an integration event.",
        math.log(20) / 0.004))
    cases.append(batch_case("BATCH-2", 0.5, 0.02, 900.0, 0.80, 300.0,
        "n = 0.5: sqrt(CA) = sqrt(CA0) - k t/2, so t = 2 sqrt(CA0)(1 - sqrt(1-X))/k; X(t) from DOP853 and t_target from an integration event.",
        2 * math.sqrt(900.0) * (1 - math.sqrt(0.2)) / 0.02))

    # McCabe-Thiele: own Underwood + stepping implementation
    for cid, q, zF, xD, xB, a, R, F in [("MCCABE-1", 1.0, 0.45, 0.95, 0.04, 2.4, 1.8, 100.0),
                                         ("MCCABE-2", 0.0, 0.40, 0.90, 0.05, 3.0, 3.0, 100.0)]:
        exp, (xl, xB_) = mccabe_independent(F, zF, xD, xB, q, a, R)
        p = dict(F=F, zF=zF, xD=xD, xB=xB, q=q, alpha=a, R=R)
        units = dict(Rmin="-", D="kmol/h", B="kmol/h", V="kmol/h", V_bar="kmol/h",
                     N_theoretical="-", feed_stage="-", N_fractional="-")
        cases.append(dict(id=cid, template="mccabe", inputs=p,
            expected={kk: [vv, units[kk]] for kk, vv in exp.items()},
            exact=["N_theoretical", "feed_stage"],
            independent=f"Constant alpha, CMO, total condenser, reboiler counted as a stage. Rmin from Underwood (theta root of sum alpha z/(alpha-theta) = 1-q); D, B, V, V' from balances (V' = V-(1-q)F); stages stepped top-down with the inverse equilibrium curve and the two operating lines (own code). Last liquid x = {xl:.4f} vs xB = {xB_}."))
    cases += new_template_cases()
    return cases


def new_template_cases():
    """CH2/CH5 templates (hx, flash, pipe, recycle), each by a method the template does
    not use for its primary result."""
    out = []

    # heat exchanger: areas from e-NTU only (the template's primary result is LMTD/F)
    def hx_case(cid, mh, cph, thi, tho, mc, cpc, tci, u, text):
        ch, cc = mh * cph, mc * cpc
        q = ch * (thi - tho)
        tco = tci + q / cc
        cmin, cmax = min(ch, cc), max(ch, cc)
        cr = cmin / cmax
        eps = q / (cmin * (thi - tci))
        ntu_ct = math.log((1 - eps * cr) / (1 - eps)) / (1 - cr)
        ntu_co = -math.log(1 - eps * (1 + cr)) / (1 + cr)
        sq = math.sqrt(1 + cr * cr)
        e = (2 / eps - (1 + cr)) / sq
        ntu_12 = -math.log((e - 1) / (e + 1)) / sq
        a_ct, a_co, a_12 = (n * cmin / u for n in (ntu_ct, ntu_co, ntu_12))
        p = dict(mh=mh, cph=cph, Th_in=thi, Th_out=tho, mc=mc, cpc=cpc, Tc_in=tci, U=u)
        return dict(id=cid, template="hx", inputs=p,
            expected={"Q": [q, "W"], "Tc_out": [tco, "K"], "A_counter": [a_ct, "m^2"],
                      "A_co": [a_co, "m^2"], "A_shell12": [a_12, "m^2"],
                      "F": [a_ct / a_12, "-"]},
            independent=text)
    out.append(hx_case("HX-1", 2.0, 2100.0, 433.15, 373.15, 2.5, 4180.0, 293.15, 350.0,
        "Golden problem P1-05 as a ChemLab case. Areas by e-NTU (counter, co-current, 1-2 shell) from the energy balance; F = A_counter / A_shell12. The template's primary result is LMTD x F."))
    out.append(hx_case("HX-2", 0.5, 2000.0, 400.0, 320.0, 1.2, 4180.0, 290.0, 250.0,
        "Oil cooler, hot stream is Cmin. Same e-NTU method; reference values also matched the ht library (MIT) to 1e-9."))

    # flash: Antoine data from the compound table, solved by closed form / polynomial roots
    sys.path.insert(0, str(HERE.parents[1] / "chemlab" / "templates"))
    from _compounds import COMPOUNDS  # data only

    def ps(num, t):
        c = COMPOUNDS[num - 1]
        return 10 ** (c["A"] - c["B"] / (t + c["C"]))

    t, p_ = 368.15, 101325.0
    p1, p2 = ps(14, t), ps(15, t)
    x1 = (p_ - p2) / (p1 - p2)
    y1 = x1 * p1 / p_
    tb = brentq(lambda tt: 0.5 * (ps(14, tt) + ps(15, tt)) - p_, 300.0, 450.0, xtol=1e-12)
    out.append(dict(id="FLASH-1", template="flash",
        inputs=dict(c1=14.0, c2=15.0, c3=0.0, n1=0.5, n2=0.5, n3=0.0, T=t, P=p_),
        expected={"x1": [x1, "-"], "y1": [y1, "-"], "V_frac": [(0.5 - x1) / (y1 - x1), "-"],
                  "T_bubble": [tb, "K"], "P_bubble": [0.5 * (p1 + p2), "Pa"]},
        independent="Benzene-toluene 50/50 at 1 atm, 95 C (Raoult, Poling Antoine). Binary closed form x1 = (P - P2)/(P1 - P2), y1 = x1 P1/P, V = (z1 - x1)/(y1 - x1); bubble T by brentq on the bubble-pressure sum (textbook: about 92 C)."))
    t3 = 360.0
    z = [0.5 / 1.3, 0.5 / 1.3, 0.3 / 1.3]
    k = [ps(n, t3) / p_ for n in (14, 15, 25)]
    poly = np.poly1d([0.0])
    for i in range(3):
        term = np.poly1d([z[i] * (k[i] - 1)])
        for j in range(3):
            if j != i:
                term = term * np.poly1d([k[j] - 1, 1.0])
        poly = poly + term
    v = [r.real for r in poly.roots if abs(r.imag) < 1e-12 and 0 < r.real < 1][0]
    xs = [zi / (1 + v * (ki - 1)) for zi, ki in zip(z, k)]
    out.append(dict(id="FLASH-2", template="flash",
        inputs=dict(c1=14.0, c2=15.0, c3=25.0, n1=0.5, n2=0.5, n3=0.3, T=t3, P=p_),
        expected={"V_frac": [v, "-"], "x1": [xs[0], "-"], "x3": [xs[2], "-"],
                  "y3": [k[2] * xs[2], "-"]},
        independent="Benzene/toluene/n-hexane at 360 K, 1 atm. Rachford-Rice multiplied out to a quadratic in V and solved with numpy roots (the template uses brentq on the sum)."))

    # pipe: Colebrook by fixed-point iteration (the template uses brentq)
    def pipe_case(cid, q, d, l, eps, rho, mu, kf, dz, eta, text):
        g = 9.80665
        uu = 4 * q / (math.pi * d * d)
        re = rho * uu * d / mu
        if re < 2300:
            f = 64 / re
        else:
            x = 8.0
            for _ in range(200):
                x = -2 * math.log10(eps / d / 3.7 + 2.51 * x / re)
            f = 1 / (x * x)
        head = f * l / d * uu * uu / (2 * g) + kf * uu * uu / (2 * g) + dz
        p = dict(Q=q, D=d, L=l, eps=eps, rho=rho, mu=mu, K_fittings=kf, dz=dz, dP=0.0, eta=eta)
        return dict(id=cid, template="pipe", inputs=p,
            expected={"Re": [re, "-"], "f_darcy": [f, "-"], "head": [head, "m"],
                      "P_shaft": [rho * g * q * head / eta, "W"]}, independent=text)
    out.append(pipe_case("PIPE-1", 0.01, 0.1, 100.0, 4.5e-5, 997.0, 8.9e-4, 5.0, 10.0, 0.7,
        "Water 10 L/s in 100 m of 100 mm commercial steel, K = 5, 10 m lift. Colebrook by fixed-point iteration on 1/sqrt(f); matches fluids.friction_factor (Clamond) to 1e-9."))
    out.append(pipe_case("PIPE-2", 1e-5, 0.05, 50.0, 4.5e-5, 997.0, 8.9e-4, 2.0, 3.0, 0.6,
        "Laminar (Re = 285): f = 64/Re by hand."))

    # recycle: brute-force successive substitution around the loop (template: fsolve)
    def recycle_case(cid, f0, yi0, xsp, sa, si, pp, text):
        f0a, f0i = f0 * (1 - yi0), f0 * yi0
        ra = ri = 0.0
        for _ in range(100000):
            na = (1 - pp) * sa * (1 - xsp) * (f0a + ra)
            ni = (1 - pp) * si * (f0i + ri)
            if abs(na - ra) < 1e-13 * max(1.0, na) and abs(ni - ri) < 1e-13 * max(1.0, ni):
                ra, ri = na, ni
                break
            ra, ri = na, ni
        pa = pp * sa * (1 - xsp) * (f0a + ra)
        prod_a = (1 - sa) * (1 - xsp) * (f0a + ra)
        p = dict(F0=f0, yI0=yi0, Xsp=xsp, sA=sa, sI=si, p=pp)
        return dict(id=cid, template="recycle", inputs=p,
            expected={"R_A": [ra, "kmol/h"], "R_I": [ri, "kmol/h"],
                      "X_overall": [(f0a - pa - prod_a) / f0a, "-"],
                      "P_total": [pp * (sa * (1 - xsp) * (f0a + ra) + si * (f0i + ri)), "kmol/h"]},
            independent=text)
    out.append(recycle_case("RECYCLE-1", 100.0, 0.01, 0.3, 0.95, 1.0, 0.05,
        "Iterate the loop (mixer, reactor, separator, splitter) by successive substitution until the recycle stops changing."))
    out.append(recycle_case("RECYCLE-2", 100.0, 0.1, 0.5, 1.0, 1.0, 0.1,
        "Hand case: R_A = 810/11, R_I = 90, X_overall = 10/11; also by successive substitution."))
    assert rel(out[-1]["expected"]["R_A"][0], 810 / 11) < 1e-9
    assert rel(out[-1]["expected"]["X_overall"][0], 10 / 11) < 1e-9
    return out


def check_template(cases):
    import importlib
    for c in cases:
        mod = importlib.import_module(f"chemlab.{c['template']}")
        r = mod.run(c["inputs"], series=False)
        assert r["ok"], (c["id"], r["errors"])
        if "n_steady_states" in c:
            assert r["n_steady_states"] == c["n_steady_states"], (c["id"], r["n_steady_states"])
        for name, (val, _u) in c["expected"].items():
            got = r["outputs"][name]["value"]
            tol = 0.0 if name in c.get("exact", []) else 0.01
            assert rel(got, val) <= tol + 1e-12, (c["id"], name, got, val)
        if "steady_states" in c:
            for s, e in zip(r["steady_states"], c["steady_states"]):
                assert rel(s["T"], e["T"]) < 0.01 and rel(s["X"], e["X"]) < 0.01
                assert s["stable"] == e["stable"]
        print(f"ok {c['id']}")


def md(problems, cases):
    L = ["# P1 golden proposals (S3)", "",
         "> These are PROPOSALS for P4's review. P4 moves accepted ones into `api/tests/golden/`; nothing here edits that folder.",
         "> Every answer is computed by two independent methods in `verify_p1_problems.py` (agree within 1e-6 relative). Run `python docs/golden-proposals/verify_p1_problems.py`.",
         "", "## Calculation problems (`p1_problems.json`)", "",
         "| id | diff | topic | answer | method 1 / method 2 |", "|---|---|---|---|---|"]
    for p in problems:
        a = p["answer"]
        L.append(f"| {p['id']} | {p['difficulty']} | {p['topic']} | {a['value']:g} {a['unit']} | {p['method_1']} / {p['method_2']} |")
    L.append("")
    for p in problems:
        L.append(f"**{p['id']}** ({p['difficulty']}): {p['question']}")
        L.append("")
    L += ["Tolerance: 1% relative for all problems.", "",
          "## ChemLab cases (`p1_chemlab_cases.json`)", "",
          "Inputs are in the templates' canonical units. Tolerance 1% on every output (integer stage counts must match exactly). The verify script runs each case through `chemlab.<template>.run` and asserts agreement.", ""]
    for c in cases:
        ex = ", ".join(f"{k} = {v[0]:.6g} {v[1]}" for k, v in c["expected"].items())
        L.append(f"- **{c['id']}** inputs `{json.dumps(c['inputs'])}`")
        L.append(f"  - expected: {ex}")
        L.append(f"  - independent calculation: {c['independent']}")
    L.append("")
    return "\n".join(L)


def main():
    problems = build_problems()
    cases = chemlab_cases()
    pub = [{k: v for k, v in p.items() if k != "_raw"} for p in problems]
    if "--write" in sys.argv:
        (HERE / "p1_problems.json").write_text(json.dumps(pub, indent=1) + "\n")
        (HERE / "p1_chemlab_cases.json").write_text(json.dumps(cases, indent=1) + "\n")
        (HERE / "p1_problems.md").write_text(md(pub, cases))
    stored = json.loads((HERE / "p1_problems.json").read_text())
    assert [s["id"] for s in stored] == [p["id"] for p in pub]
    for s, p, full in zip(stored, pub, problems):
        assert s == p, s["id"]
        assert rel(s["answer"]["value"], full["_raw"][0]) < 1e-5
        assert rel(s["answer"]["value"], full["_raw"][1]) < 1e-5
        print(f"ok {s['id']} = {full['_raw'][0]:.8g} / {full['_raw'][1]:.8g} {s['answer']['unit']}")
    sc = json.loads((HERE / "p1_chemlab_cases.json").read_text())
    assert json.loads(json.dumps(cases)) == sc, "chemlab cases JSON out of date"
    check_template(sc)
    print("ALL OK")


if __name__ == "__main__":
    main()
