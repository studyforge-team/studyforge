# P3 golden proposals (S3)

> These are PROPOSALS for P4's review. P4 moves accepted ones into `api/tests/golden/`; nothing here edits that folder.
> Every answer is computed by two independent methods in `verify_p3_problems.py` (agree within 1e-6 relative). Run `python docs/golden-proposals/verify_p3_problems.py`.
> Books: BSL = Bird, Stewart, Lightfoot, Transport Phenomena (2nd ed.); Narayanan = K. V. Narayanan, A Textbook of Chemical Engineering Thermodynamics. Every `page` is TO CONFIRM by Samarth from the physical books; no page, section or problem numbers are claimed.

## Calculation problems (`p3_problems.json`)

| id | diff | topic | book | page | answer | method 1 / method 2 |
|---|---|---|---|---|---|---|
| P3-01 | easy | ch. 2 — falling film | BSL 2nd ed., ch. 2 — falling film | TO CONFIRM (Samarth) | 0.697809 mm | delta = (3 mu q/(rho g))^(1/3) with q = Q/W; Re = 4 rho q/mu = 1.44 < 20, so smooth laminar flow / integrate the parabolic profile v(x) = rho g delta^2/(2 mu) (1 - (x/delta)^2) with quad for the flow per width, solve for delta with brentq |
| P3-02 | medium | ch. 2 — flow through an annulus | BSL 2nd ed., ch. 2 — flow through an annulus | TO CONFIRM (Samarth) | 0.626903 L/s | BSL closed form Q = pi dP R^4/(8 mu L) [(1 - k^4) - (1 - k^2)^2/ln(1/k)], k = 0.4; Re = 103 based on hydraulic diameter, laminar / solve the radial momentum balance as a boundary value problem with solve_bvp (no slip at both walls), integrate 2 pi r v dr with quad |
| P3-03 | medium | ch. 10 — wire with electrical heat source | BSL 2nd ed., ch. 10 — wire with electrical heat source | TO CONFIRM (Samarth) | 11.3082 K | Se = I^2/(ke (pi R^2)^2); dT = Se R^2/(4 k) / solve_bvp for (1/r) d/dr(r k dT/dr) + Se = 0 on [1e-5 R, R] with T(R) = 0 and zero flux at the inner end |
| P3-04 | medium | ch. 18 — diffusion through a stagnant gas film | BSL 2nd ed., ch. 18 — diffusion through a stagnant gas film | TO CONFIRM (Samarth) | 0.00104355 mol/(m^2 s) | N_A = (c D/(z2 - z1)) ln(x_B2/x_B1), c = P/(RT) / solve_bvp on d/dz[(1/(1 - x_A)) dx_A/dz] = 0 (constant-parameter form), then N_A = -c D/(1 - x_A) dx_A/dz |
| P3-05 | hard | ch. 12 — unsteady conduction, semi-infinite solid | BSL 2nd ed., ch. 12 — unsteady conduction, semi-infinite solid | TO CONFIRM (Samarth) | 123.361 °C | T = T1 + (T0 - T1) erf(x/(2 sqrt(alpha t))), written with math.erfc / method of lines on a 0.6 m domain (1200 and 2400 intervals, node at x = 0.05 m), BDF in time, Richardson extrapolation of the two grids on the temperature rise |
| P3-06 | easy | van der Waals equation | Narayanan, van der Waals equation | TO CONFIRM (Samarth) | 1.36844 L/mol | np.roots of P V^3 - (P b + R T) V^2 + a V - a b = 0, largest real root / brentq on RT/(V - b) - a/V^2 - P over a bracket from just above b to 3x the ideal-gas volume |
| P3-07 | easy | Clausius–Clapeyron equation | Narayanan, Clausius–Clapeyron equation | TO CONFIRM (Samarth) | 34.5474 kPa | ln(P/P0) = -(dH/R)(1/T - 1/Tb) / solve_ivp (DOP853) of d(ln P)/dT = dH/(R T^2) from Tb to 320 K |
| P3-08 | medium | Raoult's law — bubble point | Narayanan, Raoult's law — bubble point | TO CONFIRM (Samarth) | 95.1417 °C | brentq on sum(x_i P_i_sat(T)) - 760 over 60 to 120 °C / Newton iteration from 90 °C using the analytic derivative of the Antoine terms |
| P3-09 | medium | entropy change of an ideal gas with temperature-dependent cp | Narayanan, entropy change of an ideal gas with temperature-dependent cp | TO CONFIRM (Samarth) | 15.894 J/(mol K) | analytic: a ln(T2/T1) + b (T2 - T1) + c/2 (T2^2 - T1^2) - R ln(P2/P1) / quad of cp/T dT minus quad of R/P dP |
| P3-10 | hard | chemical reaction equilibrium — gas phase | Narayanan, chemical reaction equilibrium — gas phase | TO CONFIRM (Samarth) | 0.616784 - | brentq on y_NH3^2/(y_N2 y_H2^3) - K P^2 = 0 in the extent e (moles N2 reacted, 4 - 2e total moles) / clear denominators to 4 e^2 (4 - 2e)^2 - 27 K P^2 (1 - e)^4 = 0 and take the single real root in (0, 1) with np.roots |

**P3-01** (easy): A Newtonian liquid (viscosity 0.050 Pa s, density 900 kg/m^3) flows as a steady laminar film down a vertical wall at 2.0e-5 m^2/s of volumetric flow per unit width of wall (use g = 9.81 m/s^2, no ripples, negligible end effects). What is the film thickness in mm?

**P3-02** (medium): A Newtonian oil (viscosity 0.10 Pa s, density 900 kg/m^3) flows by laminar axial flow through a horizontal concentric annulus with outer radius 25 mm and inner radius 10 mm. The pressure drop is 2000 Pa per metre of length. What is the volumetric flow rate in L/s?

**P3-03** (medium): A long stainless-steel wire of radius 1.5 mm (thermal conductivity 16 W/(m K), electrical conductivity 1.4e6 S/m) carries a current of 150 A. Heat is generated uniformly and removed at the surface, which is held at a constant temperature; assume constant properties and radial conduction only. By how many kelvin is the centreline hotter than the surface?

**P3-04** (medium): In an Arnold diffusion cell, liquid A evaporates into stagnant gas B at 328 K and 101325 Pa total pressure. The vapour pressure of A at the liquid surface is 30.0 kPa, and the gas composition at the top of the 0.15 m column is pure B (x_A = 0). The binary diffusivity is 1.2e-5 m^2/s. Use R = 8.314462618 J/(mol K) and ideal gas for the gas phase. What is the molar flux of A in mol/(m^2 s)?

**P3-05** (hard): A semi-infinite solid with thermal diffusivity 1.1e-6 m^2/s is initially at 20 °C. Its surface is suddenly raised to 200 °C and held there. What is the temperature, in °C, at a depth of 0.050 m after 3600 s?

**P3-06** (easy): Using the van der Waals equation with a = 27 R^2 Tc^2/(64 Pc) and b = R Tc/(8 Pc), find the molar volume of CO2 gas at 350 K and 20 bar. Take Tc = 304.2 K, Pc = 73.8 bar and R = 0.0831446 L bar/(mol K). Give the vapour-like (largest) root in L/mol.

**P3-07** (easy): A liquid has a constant enthalpy of vaporisation of 33.5 kJ/mol and a normal boiling point (101.325 kPa) of 349.9 K. Using the Clausius–Clapeyron equation with ideal vapour and R = 8.314 J/(mol K), find its vapour pressure at 320 K in kPa.

**P3-08** (medium): A liquid mixture of 40 mol% benzene and 60 mol% toluene is at a total pressure of 101.325 kPa (760 mmHg). Assume ideal solution (Raoult's law) with Antoine equation log10 P_sat [mmHg] = A - B/(T [°C] + C), benzene A = 6.90565, B = 1211.033, C = 220.790, toluene A = 6.95464, B = 1344.8, C = 219.482. What is the bubble-point temperature in °C?

**P3-09** (medium): An ideal gas with cp = a + b T + c T^2 in J/(mol K), where a = 25.0, b = 0.035 and c = -1.0e-5 (T in K), is heated and compressed from 300 K and 1 bar to 700 K and 8 bar. With R = 8.314 J/(mol K), what is the entropy change in J/(mol K)?

**P3-10** (hard): N2 + 3 H2 <=> 2 NH3 takes place in the ideal-gas phase from a stoichiometric feed of 1 mol N2 and 3 mol H2 at a constant total pressure of 100 bar. At the reaction temperature the equilibrium constant, with standard state 1 bar, is K = 2.0e-3. What is the equilibrium fractional conversion of N2?

Tolerance: 1% relative for all problems.
