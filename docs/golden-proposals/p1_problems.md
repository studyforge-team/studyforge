# P1 golden proposals (S3)

> These are PROPOSALS for P4's review. P4 moves accepted ones into `api/tests/golden/`; nothing here edits that folder.
> Every answer is computed by two independent methods in `verify_p1_problems.py` (agree within 1e-6 relative). Run `python docs/golden-proposals/verify_p1_problems.py`.

## Calculation problems (`p1_problems.json`)

| id | diff | topic | answer | method 1 / method 2 |
|---|---|---|---|---|
| P1-01 | easy | CRE: batch reactor, first order | 51.1686 min | t = ln(1/(1-X))/k / solve_ivp dCA/dt = -k CA with a stop event at CA/CA0 = 0.1 |
| P1-02 | easy | Thermodynamics: ideal gas | 72.1634 mol | n = PV/(RT) in SI (Pa, m^3, J/mol/K) / n = PV/(RT) in bar, litres, R = 0.0831446 L bar/(mol K) |
| P1-03 | easy | Fluid flow: laminar pipe | 52.1519 kPa | Hagen-Poiseuille dP = 128 mu L Q/(pi D^4); Re = 560 so laminar / Darcy-Weisbach with f = 64/Re |
| P1-04 | easy | Heat transfer: composite wall | 1000.68 W/m^2 | q = dT / sum(L/k) / solve the two interface temperatures as a linear system, then q = k dT/L in layer 1 |
| P1-05 | medium | Heat transfer: counter-current exchanger | 7.43518 m^2 | Q = U A LMTD (counter-current) / effectiveness-NTU, counter-flow formula, A = NTU Cmin/U |
| P1-06 | medium | Thermodynamics: isentropic compression | 201.456 kJ/kg | w = gamma/(gamma-1) R T1 [(P2/P1)^((gamma-1)/gamma) - 1] / numerical integral of v dP along P v^gamma = const |
| P1-07 | medium | Separations: flash | 0.490018 - | Rachford-Rice equation solved with brentq on [0, 1] / Rachford-Rice cleared of denominators, polynomial roots, root in [0, 1] |
| P1-08 | medium | CRE: CSTRs in series | 72.2992 % | X = 1 - 1/(1 + k tau)^2 with tau = 7.5 min / simultaneous steady-state mole balances solved with fsolve |
| P1-09 | hard | Maths: nonlinear ODE initial value problem | 3.95152 - | Bernoulli substitution u = y^-2 gives a linear ODE with a closed form / scipy solve_ivp, DOP853, rtol 1e-13 |
| P1-10 | hard | Maths: root of a nonlinear equation | 1.14223 rad | brentq on x tan x - 2.5 over (0.1, pi/2) / Newton iteration on x sin x - 2.5 cos x (no pole) |

**P1-01** (easy): A first-order liquid-phase reaction A -> B runs in a well-mixed batch reactor with k = 0.045 min^-1. How long does it take to reach 90% conversion of A? Give the answer in minutes.

**P1-02** (easy): A 0.50 m^3 tank holds nitrogen at 350 K and 4.2 bar absolute. Treating it as an ideal gas, how many moles of nitrogen are in the tank?

**P1-03** (easy): Oil (viscosity 0.080 Pa s, density 880 kg/m^3) flows at 2.0 L/s through a 50 m long horizontal pipe of 0.050 m inside diameter. What is the pressure drop in kPa?

**P1-04** (easy): A furnace wall has 0.23 m of firebrick (k = 1.1 W/(m K)), 0.12 m of insulating brick (k = 0.15 W/(m K)) and a 10 mm steel plate (k = 45 W/(m K)). The hot face is at 1100 C and the outer steel surface is at 90 C. What is the heat loss per square metre of wall in W/m^2?

**P1-05** (medium): Hot oil (2.0 kg/s, cp = 2.1 kJ/(kg K)) is cooled from 160 C to 100 C in a counter-current heat exchanger by water (2.5 kg/s, cp = 4.18 kJ/(kg K)) entering at 20 C. U = 350 W/(m^2 K). What heat transfer area is needed, in m^2?

**P1-06** (medium): Air (ideal gas, R = 0.287 kJ/(kg K), gamma = 1.4) enters a reversible adiabatic compressor at 100 kPa and 300 K and leaves at 600 kPa. What is the shaft work per kg of air in kJ/kg?

**P1-07** (medium): A liquid feed with mole fractions 0.30 (A), 0.40 (B) and 0.30 (C) is flashed isothermally. The K-values at flash conditions are K_A = 3.2, K_B = 1.1, K_C = 0.25. What fraction of the feed leaves as vapour (V/F)?

**P1-08** (medium): Two equal CSTRs of 150 L each are in series. A first-order reaction A -> B with k = 0.12 min^-1 occurs in liquid fed at 20 L/min. What is the overall conversion of A leaving the second reactor, in percent?

**P1-09** (hard): Solve dy/dt = 0.8 y - 0.05 y^3 with y(0) = 2. What is y(3)?

**P1-10** (hard): Find the smallest positive root of x tan(x) = 2.5, with x in radians (the first eigenvalue for a slab with Biot number 2.5).

Tolerance: 1% relative for all problems.

## ChemLab cases (`p1_chemlab_cases.json`)

Inputs are in the templates' canonical units. Tolerance 1% on every output (integer stage counts must match exactly). The verify script runs each case through `chemlab.<template>.run` and asserts agreement.

- **CSTR-1** inputs `{"CA0": 1500.0, "v0": 0.02, "V": 3.0, "n": 2.0, "k0": 50.0, "Ea": 40000.0, "T0": 320.0, "isothermal": 1.0}`
  - expected: X = 0.58178 -, CA = 627.33 mol/m^3, tau = 150 s, Da = 3.32621 -
  - independent calculation: Isothermal 2nd-order CSTR: X = (2Da+1-sqrt(4Da+1))/(2Da), Da = k tau CA0; checked by integrating dCA/dt to steady state with LSODA.
- **CSTR-2** inputs `{"CA0": 2000.0, "v0": 0.01, "V": 1.0, "n": 1.0, "k0": 10000000000.0, "Ea": 80000.0, "dHr": -200000.0, "rho_cp": 4180000.0, "UA": 0.0, "Ta": 300.0, "T0": 300.0, "isothermal": 0.0}`
  - expected: T = 301.273 K, X = 0.0133074 -
  - independent calculation: First order, adiabatic: X = Da/(1+Da) and T = T0 + dT_ad X, so roots of dT_ad Da(T)/(1+Da(T)) - (T - T0) in T, scanned on a grid and refined with brentq. Stability from the sign of d(G-R)/dT. Outputs are the lowest-T stable state.
- **PFR-1** inputs `{"CA0": 800.0, "v0": 0.002, "V": 0.5, "D": 0.1, "n": 1.0, "k": 0.012}`
  - expected: X = 0.950213 -, CA = 39.8297 mol/m^3, tau = 250 s, length_m = 63.662 m
  - independent calculation: First order: integrate v0 dCA/dV = -k CA with DOP853; cross-checked against X = 1 - exp(-k tau).
- **PFR-2** inputs `{"CA0": 1200.0, "v0": 0.002, "V": 0.8, "D": 0.1, "n": 2.0, "k": 1e-05}`
  - expected: X = 0.827586 -, CA = 206.897 mol/m^3, tau = 400 s, length_m = 101.859 m
  - independent calculation: Second order: integrate v0 dCA/dV = -k CA^2 with DOP853; cross-checked against X = Da/(1+Da), Da = k tau CA0.
- **BATCH-1** inputs `{"CA0": 1000.0, "V": 0.5, "n": 1.0, "k": 0.004, "t": 300.0, "X_target": 0.95}`
  - expected: t_for_target = 748.933 s, X = 0.698806 -
  - independent calculation: First order: t = ln(1/(1-X))/k = 748.9 s; X(t) from DOP853; t_target also found by an integration event.
- **BATCH-2** inputs `{"CA0": 900.0, "V": 0.5, "n": 0.5, "k": 0.02, "t": 300.0, "X_target": 0.8}`
  - expected: t_for_target = 1658.36 s, X = 0.19 -
  - independent calculation: n = 0.5: sqrt(CA) = sqrt(CA0) - k t/2, so t = 2 sqrt(CA0)(1 - sqrt(1-X))/k; X(t) from DOP853 and t_target from an integration event.
- **MCCABE-1** inputs `{"F": 100.0, "zF": 0.45, "xD": 0.95, "xB": 0.04, "q": 1.0, "alpha": 2.4, "R": 1.8}`
  - expected: Rmin = 1.35209 -, D = 45.0549 kmol/h, B = 54.9451 kmol/h, V = 126.154 kmol/h, V_bar = 126.154 kmol/h, N_theoretical = 14 -, feed_stage = 7 -, N_fractional = 13.9517 -
  - independent calculation: Constant alpha, CMO, total condenser, reboiler counted as a stage. Rmin from Underwood (theta root of sum alpha z/(alpha-theta) = 1-q); D, B, V, V' from balances (V' = V-(1-q)F); stages stepped top-down with the inverse equilibrium curve and the two operating lines (own code). Last liquid x = 0.0383 vs xB = 0.04.
- **MCCABE-2** inputs `{"F": 100.0, "zF": 0.4, "xD": 0.9, "xB": 0.05, "q": 0.0, "alpha": 3.0, "R": 3.0}`
  - expected: Rmin = 2.29167 -, D = 41.1765 kmol/h, B = 58.8235 kmol/h, V = 164.706 kmol/h, V_bar = 64.7059 kmol/h, N_theoretical = 8 -, feed_stage = 5 -, N_fractional = 7.77184 -
  - independent calculation: Constant alpha, CMO, total condenser, reboiler counted as a stage. Rmin from Underwood (theta root of sum alpha z/(alpha-theta) = 1-q); D, B, V, V' from balances (V' = V-(1-q)F); stages stepped top-down with the inverse equilibrium curve and the two operating lines (own code). Last liquid x = 0.0404 vs xB = 0.05.
