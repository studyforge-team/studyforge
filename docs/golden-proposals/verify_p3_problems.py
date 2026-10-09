"""Recompute every P3 golden proposal two independent ways and check the JSON file.

    python docs/golden-proposals/verify_p3_problems.py          # verify (CI-style)
    python docs/golden-proposals/verify_p3_problems.py --write  # regenerate JSON + md

Needs numpy and scipy only. 10 calculation problems (transport + thermodynamics), method 1 vs
method 2 within 1e-6 relative, then vs p3_problems.json
(6 significant digits stored, compared at 1e-5).
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad, solve_bvp, solve_ivp
from scipy.optimize import brentq
from scipy.sparse import diags

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
G = 9.81


def rel(a, b):
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


def p01():
    mu, rho, q = 0.05, 900.0, 2.0e-5  # q = Q/W, m^2/s
    d1 = (3 * mu * q / (rho * G)) ** (1 / 3)
    assert 4 * rho * q / mu < 20  # Re = 1.44
    flow = lambda d: quad(lambda x: rho * G * d**2 / (2 * mu) * (1 - (x / d) ** 2), 0, d,
                          epsabs=0, epsrel=1e-13)[0]
    d2 = brentq(lambda d: flow(d) - q, 1e-5, 1e-2, xtol=1e-16, rtol=1e-14)
    return d1 * 1e3, d2 * 1e3


def p02():
    mu, G_, R, k = 0.10, 2000.0, 0.025, 0.4  # G_ = (P0-PL)/L
    m1 = math.pi * G_ * R**4 / (8 * mu) * ((1 - k**4) - (1 - k**2) ** 2 / math.log(1 / k))
    # w = r dv/dr ; v' = w/r ; w' = -G r/mu ; v = 0 at both walls
    f = lambda r, y: np.vstack([y[1] / r, -G_ * r / mu * np.ones_like(r)])
    bc = lambda ya, yb: np.array([ya[0], yb[0]])
    r = np.linspace(k * R, R, 400)
    s = solve_bvp(f, bc, r, np.zeros((2, r.size)), tol=1e-9, max_nodes=200000)
    assert s.success
    m2 = quad(lambda x: 2 * math.pi * x * s.sol(x)[0], k * R, R, epsabs=0, epsrel=1e-12)[0]
    assert 900.0 * (m1 / (math.pi * R**2 * (1 - k**2))) * 2 * R * (1 - k) / mu < 2000  # Re ~ 103
    return m1 * 1e3, m2 * 1e3


def p03():
    I, R, ke, k = 150.0, 1.5e-3, 1.4e6, 16.0
    Se = I**2 / (ke * (math.pi * R**2) ** 2)
    m1 = Se * R**2 / (4 * k)
    r0 = 1e-5 * R
    f = lambda r, y: np.vstack([y[1] / (k * r), -Se * r])  # y = [T, r k dT/dr]
    bc = lambda ya, yb: np.array([ya[1] + Se * r0**2 / 2, yb[0]])  # flux ~0 at r0, T(R)=0
    r = np.linspace(r0, R, 400)
    s = solve_bvp(f, bc, r, np.zeros((2, r.size)), tol=1e-9, max_nodes=200000)
    assert s.success
    return m1, float(s.y[0, 0])


def p04():
    P, T, D, z, pv = 101325.0, 328.0, 1.2e-5, 0.15, 30.0e3
    R, x1 = 8.314462618, pv / P
    c = P / (R * T)
    m1 = c * D / z * math.log(1 / (1 - x1))
    # (1/(1-x)) dx/dz = C constant (parameter); x(0)=x1, x(z)=0
    f = lambda zz, y, p: np.vstack([(1 - y[0]) * p[0]])
    bc = lambda ya, yb, p: np.array([ya[0] - x1, yb[0]])
    zz = np.linspace(0, z, 50)
    s = solve_bvp(f, bc, zz, np.full((1, zz.size), x1) * (1 - zz / z), p=[-1.0], tol=1e-9)
    assert s.success
    return m1, float(-c * D * s.p[0])


def p05():
    al, T0, T1, x, t = 1.1e-6, 20.0, 200.0, 0.05, 3600.0
    m1 = T1 + (T0 - T1) * (1 - math.erfc(x / (2 * math.sqrt(al * t))))
    L = 0.6

    def mol(N):
        h = L / N
        n = N - 1  # interior nodes; theta(0)=1, theta(L)=0, theta0=0
        A = diags([1.0, -2.0, 1.0], [-1, 0, 1], shape=(n, n), format="csc") * (al / h**2)
        b = np.zeros(n)
        b[0] = al / h**2
        s = solve_ivp(lambda tt, th: A @ th + b, (0, t), np.zeros(n), method="BDF",
                      jac=A, rtol=1e-9, atol=1e-14)
        return s.y[round(x / h) - 1, -1]

    a, b2 = mol(1200), mol(2400)  # both put a node at x = 0.05
    th = (4 * b2 - a) / 3  # Richardson (h^2)
    return m1, T0 + (T1 - T0) * th


def p06():
    Tc, Pc, R, T, P = 304.2, 73.8, 0.0831446, 350.0, 20.0
    a, b = 27 * R**2 * Tc**2 / (64 * Pc), R * Tc / (8 * Pc)
    roots = np.roots([P, -(P * b + R * T), a, -a * b])
    m1 = max(r.real for r in roots if abs(r.imag) < 1e-9)
    m2 = brentq(lambda V: R * T / (V - b) - a / V**2 - P, b * 1.0001, 3 * R * T / P, xtol=1e-15)
    return m1, m2


def p07():
    dH, Tb, T, R = 33500.0, 349.9, 320.0, 8.314
    m1 = 101.325 * math.exp(-dH / R * (1 / T - 1 / Tb))
    s = solve_ivp(lambda tt, y: [dH / (R * tt**2)], (Tb, T), [math.log(101.325)],
                  method="DOP853", rtol=1e-13, atol=1e-14)
    return m1, math.exp(s.y[0, -1])


ANT = [(6.90565, 1211.033, 220.790), (6.95464, 1344.8, 219.482)]  # benzene, toluene


def p08():
    x = [0.40, 0.60]
    Ps = lambda i, T: 10 ** (ANT[i][0] - ANT[i][1] / (T + ANT[i][2]))
    F = lambda T: sum(x[i] * Ps(i, T) for i in range(2)) - 760.0
    m1 = brentq(F, 60, 120, xtol=1e-14)
    T = 90.0
    for _ in range(50):
        dF = sum(x[i] * Ps(i, T) * math.log(10) * ANT[i][1] / (T + ANT[i][2]) ** 2 for i in range(2))
        T -= F(T) / dF
    return m1, T


def p09():
    a, b, c, T1, T2, P1, P2, R = 25.0, 0.035, -1.0e-5, 300.0, 700.0, 1.0, 8.0, 8.314
    m1 = a * math.log(T2 / T1) + b * (T2 - T1) + c / 2 * (T2**2 - T1**2) - R * math.log(P2 / P1)
    m2 = quad(lambda T: (a + b * T + c * T * T) / T, T1, T2, epsabs=0, epsrel=1e-13)[0] \
        - quad(lambda P: R / P, P1, P2, epsabs=0, epsrel=1e-13)[0]
    return m1, m2


def p10():
    K, P = 2.0e-3, 100.0
    kp2 = K * P * P
    ratio = lambda e: 4 * e**2 * (4 - 2 * e) ** 2 / (27 * (1 - e) ** 4)
    m1 = brentq(lambda e: ratio(e) - kp2, 1e-9, 1 - 1e-9, xtol=1e-15)
    Pn = np.polynomial.Polynomial
    poly = 4 * Pn([0, 1]) ** 2 * Pn([4, -2]) ** 2 - 27 * kp2 * Pn([1, -1]) ** 4
    roots = [r.real for r in poly.roots() if abs(r.imag) < 1e-9 and 0 < r.real < 1]
    assert len(roots) == 1
    return m1, roots[0]


B, N = "Transport: ", "Thermodynamics: "
# (id, difficulty, topic, subject prefix, fn, unit, method agreement, question, method_1, method_2)
PROBLEMS = [
    ("P3-01", "easy", "falling film", B, p01, "mm", 1e-6,
     "A Newtonian liquid (viscosity 0.050 Pa s, density 900 kg/m^3) flows as a steady laminar film down a vertical wall at 2.0e-5 m^2/s of volumetric flow per unit width of wall (use g = 9.81 m/s^2, no ripples, negligible end effects). What is the film thickness in mm?",
     "delta = (3 mu q/(rho g))^(1/3) with q = Q/W; Re = 4 rho q/mu = 1.44 < 20, so smooth laminar flow",
     "integrate the parabolic profile v(x) = rho g delta^2/(2 mu) (1 - (x/delta)^2) with quad for the flow per width, solve for delta with brentq"),
    ("P3-02", "medium", "flow through an annulus", B, p02, "L/s", 1e-6,
     "A Newtonian oil (viscosity 0.10 Pa s, density 900 kg/m^3) flows by laminar axial flow through a horizontal concentric annulus with outer radius 25 mm and inner radius 10 mm. The pressure drop is 2000 Pa per metre of length. What is the volumetric flow rate in L/s?",
     "closed form Q = pi dP R^4/(8 mu L) [(1 - k^4) - (1 - k^2)^2/ln(1/k)], k = 0.4; Re = 103 based on hydraulic diameter, laminar",
     "solve the radial momentum balance as a boundary value problem with solve_bvp (no slip at both walls), integrate 2 pi r v dr with quad"),
    ("P3-03", "medium", "wire with electrical heat source", B, p03, "K", 1e-6,
     "A long stainless-steel wire of radius 1.5 mm (thermal conductivity 16 W/(m K), electrical conductivity 1.4e6 S/m) carries a current of 150 A. Heat is generated uniformly and removed at the surface, which is held at a constant temperature; assume constant properties and radial conduction only. By how many kelvin is the centreline hotter than the surface?",
     "Se = I^2/(ke (pi R^2)^2); dT = Se R^2/(4 k)",
     "solve_bvp for (1/r) d/dr(r k dT/dr) + Se = 0 on [1e-5 R, R] with T(R) = 0 and zero flux at the inner end"),
    ("P3-04", "medium", "diffusion through a stagnant gas film", B, p04, "mol/(m^2 s)", 1e-6,
     "In an Arnold diffusion cell, liquid A evaporates into stagnant gas B at 328 K and 101325 Pa total pressure. The vapour pressure of A at the liquid surface is 30.0 kPa, and the gas composition at the top of the 0.15 m column is pure B (x_A = 0). The binary diffusivity is 1.2e-5 m^2/s. Use R = 8.314462618 J/(mol K) and ideal gas for the gas phase. What is the molar flux of A in mol/(m^2 s)?",
     "N_A = (c D/(z2 - z1)) ln(x_B2/x_B1), c = P/(RT)",
     "solve_bvp on d/dz[(1/(1 - x_A)) dx_A/dz] = 0 (constant-parameter form), then N_A = -c D/(1 - x_A) dx_A/dz"),
    ("P3-05", "hard", "unsteady conduction, semi-infinite solid", B, p05, "°C", 1e-6,
     "A semi-infinite solid with thermal diffusivity 1.1e-6 m^2/s is initially at 20 °C. Its surface is suddenly raised to 200 °C and held there. What is the temperature, in °C, at a depth of 0.050 m after 3600 s?",
     "T = T1 + (T0 - T1) erf(x/(2 sqrt(alpha t))), written with math.erfc",
     "method of lines on a 0.6 m domain (1200 and 2400 intervals, node at x = 0.05 m), BDF in time, Richardson extrapolation of the two grids on the temperature rise"),
    ("P3-06", "easy", "van der Waals equation", N, p06, "L/mol", 1e-6,
     "Using the van der Waals equation with a = 27 R^2 Tc^2/(64 Pc) and b = R Tc/(8 Pc), find the molar volume of CO2 gas at 350 K and 20 bar. Take Tc = 304.2 K, Pc = 73.8 bar and R = 0.0831446 L bar/(mol K). Give the vapour-like (largest) root in L/mol.",
     "np.roots of P V^3 - (P b + R T) V^2 + a V - a b = 0, largest real root",
     "brentq on RT/(V - b) - a/V^2 - P over a bracket from just above b to 3x the ideal-gas volume"),
    ("P3-07", "easy", "Clausius–Clapeyron equation", N, p07, "kPa", 1e-6,
     "A liquid has a constant enthalpy of vaporisation of 33.5 kJ/mol and a normal boiling point (101.325 kPa) of 349.9 K. Using the Clausius–Clapeyron equation with ideal vapour and R = 8.314 J/(mol K), find its vapour pressure at 320 K in kPa.",
     "ln(P/P0) = -(dH/R)(1/T - 1/Tb)",
     "solve_ivp (DOP853) of d(ln P)/dT = dH/(R T^2) from Tb to 320 K"),
    ("P3-08", "medium", "Raoult's law — bubble point", N, p08, "°C", 1e-6,
     "A liquid mixture of 40 mol% benzene and 60 mol% toluene is at a total pressure of 101.325 kPa (760 mmHg). Assume ideal solution (Raoult's law) with Antoine equation log10 P_sat [mmHg] = A - B/(T [°C] + C), benzene A = 6.90565, B = 1211.033, C = 220.790, toluene A = 6.95464, B = 1344.8, C = 219.482. What is the bubble-point temperature in °C?",
     "brentq on sum(x_i P_i_sat(T)) - 760 over 60 to 120 °C",
     "Newton iteration from 90 °C using the analytic derivative of the Antoine terms"),
    ("P3-09", "medium", "entropy change of an ideal gas with temperature-dependent cp", N, p09, "J/(mol K)", 1e-6,
     "An ideal gas with cp = a + b T + c T^2 in J/(mol K), where a = 25.0, b = 0.035 and c = -1.0e-5 (T in K), is heated and compressed from 300 K and 1 bar to 700 K and 8 bar. With R = 8.314 J/(mol K), what is the entropy change in J/(mol K)?",
     "analytic: a ln(T2/T1) + b (T2 - T1) + c/2 (T2^2 - T1^2) - R ln(P2/P1)",
     "quad of cp/T dT minus quad of R/P dP"),
    ("P3-10", "hard", "chemical reaction equilibrium — gas phase", N, p10, "-", 1e-6,
     "N2 + 3 H2 <=> 2 NH3 takes place in the ideal-gas phase from a stoichiometric feed of 1 mol N2 and 3 mol H2 at a constant total pressure of 100 bar. At the reaction temperature the equilibrium constant, with standard state 1 bar, is K = 2.0e-3. What is the equilibrium fractional conversion of N2?",
     "brentq on y_NH3^2/(y_N2 y_H2^3) - K P^2 = 0 in the extent e (moles N2 reacted, 4 - 2e total moles)",
     "clear denominators to 4 e^2 (4 - 2e)^2 - 27 K P^2 (1 - e)^4 = 0 and take the single real root in (0, 1) with np.roots"),
]


def sig(x, n=6):
    return float(f"{x:.{n - 1}e}")


def build():
    out = []
    for pid, diff, topic, subject, fn, unit, tol, q, t1, t2 in PROBLEMS:
        a, b = fn()
        assert rel(a, b) < tol, (pid, a, b, rel(a, b))
        out.append({
            "id": pid, "question": q, "answer": {"value": sig(a), "unit": unit},
            "tolerance_rel": 0.01, "method_1": t1, "method_2": t2,
            "topic": subject + topic, "difficulty": diff,
            "source_note": "textbook topic; numbers original",
            "_raw": (a, b),
        })
    return out


def md(P):
    L = ["# P3 golden proposals (S3)", "",
         "> These are PROPOSALS for P4's review. P4 moves accepted ones into `api/tests/golden/`; nothing here edits that folder.",
         "> Every answer is computed by two independent methods in `verify_p3_problems.py` (agree within 1e-6 relative). Run `python docs/golden-proposals/verify_p3_problems.py`.",
         "", "## Calculation problems (`p3_problems.json`)", "",
         "| id | diff | topic | answer | method 1 / method 2 |", "|---|---|---|---|---|"]
    for p in P:
        a = p["answer"]
        L.append(f"| {p['id']} | {p['difficulty']} | {p['topic']} | {a['value']:g} {a['unit']} | {p['method_1']} / {p['method_2']} |")
    L.append("")
    for p in P:
        L += [f"**{p['id']}** ({p['difficulty']}): {p['question']}", ""]
    L += ["Tolerance: 1% relative for all problems.", ""]
    return "\n".join(L)


def main():
    full = build()
    pub = [{k: v for k, v in p.items() if k != "_raw"} for p in full]
    if "--write" in sys.argv:
        (HERE / "p3_problems.json").write_text(json.dumps(pub, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (HERE / "p3_problems.md").write_text(md(pub), encoding="utf-8")
    stored = json.loads((HERE / "p3_problems.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in stored] == [p["id"] for p in pub]
    for s, p, f in zip(stored, pub, full):
        assert s == p, s["id"]
        assert rel(s["answer"]["value"], f["_raw"][0]) < 1e-5
        assert rel(s["answer"]["value"], f["_raw"][1]) < 1e-5
        print(f"ok {s['id']} = {f['_raw'][0]:.8g} / {f['_raw'][1]:.8g} {s['answer']['unit']}")
    print("ALL OK")


if __name__ == "__main__":
    main()
