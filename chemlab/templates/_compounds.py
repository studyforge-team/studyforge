"""Compound data for ChemLab templates. GENERATED, do not edit by hand:
run chemlab/tools/export_compounds.py (chemicals 1.5.2).

A, B, C, Tmin, Tmax (and src antoine) are None when there is no Poling Antoine row; Tb,
Tc, Pc, omega are None (src None) when fewer than 2 data tables exist.
Units: MW kg/kmol, Tc K, Pc Pa, omega -, Tb K (normal boiling point), Antoine
log10(Psat/Pa) = A - B/(T + C) with T in K, valid for Tmin <= T <= Tmax.
"cp" = [a0..a4], ideal-gas Cp/R = a0 + a1 T + a2 T^2 + a3 T^3 + a4 T^4 (T in K,
Cp in J/mol/K = R * that, R = 8.314462618 J/mol/K), valid cp_Tmin <= T <= cp_Tmax.
"src" names the table each value came from (see SOURCES): the first preferred
table that agrees with the median of all data tables in chemicals (see the
exporter). The omega, Tc/Pc, Tb and Antoine values of a row can come from
different tables.

WATER_1ATM: liquid water at 1 atm, rows of WATER_COLUMNS (T_C degC, rho kg/m3,
cp J/kg/K, mu Pa s, k W/m/K, Pr -); the 100 degC row is saturated liquid at
101.42 kPa (1 atm is just below its vapour pressure). Source IAPWS (see SOURCES).

FULLER_*: diffusion volumes in cm3/mol for the Fuller-Schettler-Giddings method,
Poling, Prausnitz, O'Connell, The Properties of Gases and Liquids, 5th ed.,
Table 11-1 (atoms, rings, simple molecules)."""

from typing import Any

# fmt: off
SOURCES: dict[str, str] = {
    'IUPAC': "IUPAC critically evaluated series 'Vapor-Liquid Critical Properties of Elements and Compounds' parts 1-12, J. Chem. Eng. Data (1995-2015)",
    'MATTHEWS': 'Mathews, Critical Constants of Inorganic Substances, Chem. Rev. 72 (1972) 71-100',
    'CRC': 'Haynes, Bruno, Lide, CRC Handbook of Chemistry and Physics, 95th ed. (2014)',
    'PSRK': 'Horstmann et al., PSRK Group Contribution Equation of State revision IV, Fluid Phase Equilib. 227 (2005) 157-164 (experimental and estimated values)',
    'POLING': "Poling, Prausnitz, O'Connell, The Properties of Gases and Liquids, 5th ed. (2000), Antoine constants converted to log10(P/Pa) = A - B/(T/K + C)",
    'HEOS': 'reference equations of state as in NIST REFPROP (critical point and acentric factor of the equation)',
    'CRC_ORG': 'Haynes, Bruno, Lide, CRC Handbook of Chemistry and Physics, 95th ed. (2014), physical constants of organic compounds',
    'CRC_INORG': 'Haynes, Bruno, Lide, CRC Handbook of Chemistry and Physics, 95th ed. (2014), physical constants of inorganic compounds',
    'POLING_CP': "Poling, Prausnitz, O'Connell, The Properties of Gases and Liquids, 5th ed. (2000), ideal-gas heat capacity polynomial Cp/R = a0 + a1 T + a2 T^2 + a3 T^3 + a4 T^4",
    'IAPWS': 'IAPWS-95 (density, Cp), IAPWS 2008 viscosity release, IAPWS 2011 thermal conductivity release, as implemented in chemicals',
    'FORMULA': 'molar mass from the formula, IUPAC 2007 atomic weights as tabulated in chemicals',
}

COMPOUNDS: tuple[dict[str, Any], ...] = (
    {'name': 'water', 'cas': '7732-18-5', 'formula': 'H2O', 'MW': 18.01528, 'Tc': 647.096, 'Pc': 22064000.0, 'omega': 0.3443, 'A': 10.11564, 'B': 1687.537, 'C': -42.98, 'Tmin': 273.2, 'Tmax': 473.2, 'Tb': 373.124295848, 'cp': [4.395, -0.004186, 1.405e-05, -1.564e-08, 6.32e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'methanol', 'cas': '67-56-1', 'formula': 'CH4O', 'MW': 32.04186, 'Tc': 513.38, 'Pc': 8215850.0, 'omega': 0.5625, 'A': 10.20277, 'B': 1580.08, 'C': -33.65, 'Tmin': 262.59, 'Tmax': 356.0, 'Tb': 337.632383296, 'cp': [4.714, -0.006986, 4.211e-05, -4.443e-08, 1.535e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'ethanol', 'cas': '64-17-5', 'formula': 'C2H6O', 'MW': 46.06844, 'Tc': 514.71, 'Pc': 6268000.0, 'omega': 0.646, 'A': 10.33675, 'B': 1648.22, 'C': -42.232, 'Tmin': 276.5, 'Tmax': 369.54, 'Tb': 351.570441659, 'cp': [4.396, 0.000628, 5.546e-05, -7.024e-08, 2.685e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': '1-propanol', 'cas': '71-23-8', 'formula': 'C3H8O', 'MW': 60.09502, 'Tc': 536.8, 'Pc': 5169000.0, 'omega': 0.624, 'A': 9.99991, 'B': 1512.94, 'C': -67.343, 'Tmin': 293.19, 'Tmax': 389.32, 'Tb': 370.19, 'cp': [4.712, 0.006565, 6.31e-05, -8.341e-08, 3.216e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': '2-propanol', 'cas': '67-63-0', 'formula': 'C3H8O', 'MW': 60.09502, 'Tc': 508.3, 'Pc': 4764000.0, 'omega': 0.665, 'A': 10.24268, 'B': 1580.92, 'C': -53.54, 'Tmin': 281.28, 'Tmax': 373.46, 'Tb': 355.36, 'cp': [3.334, 0.018853, 3.644e-05, -6.115e-08, 2.543e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': '1-butanol', 'cas': '71-36-3', 'formula': 'C4H10O', 'MW': 74.1216, 'Tc': 563.0, 'Pc': 4414000.0, 'omega': 0.59, 'A': 9.6493, 'B': 1395.14, 'C': -90.411, 'Tmin': 310.18, 'Tmax': 411.26, 'Tb': 390.75, 'cp': [4.467, 0.016395, 6.688e-05, -9.69e-08, 3.864e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'acetone', 'cas': '67-64-1', 'formula': 'C3H6O', 'MW': 58.07914, 'Tc': 508.1, 'Pc': 4692400.0, 'omega': 0.3071, 'A': 9.2184, 'B': 1197.01, 'C': -45.09, 'Tmin': 247.38, 'Tmax': 350.65, 'Tb': 329.224922705, 'cp': [5.126, 0.001511, 5.731e-05, -7.177e-08, 2.728e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'methyl ethyl ketone', 'cas': '78-93-3', 'formula': 'C4H8O', 'MW': 72.10572, 'Tc': 536.7, 'Pc': 4207000.0, 'omega': 0.329, 'A': 9.1386, 'B': 1232.63, 'C': -54.46, 'Tmin': 265.62, 'Tmax': 375.66, 'Tb': 352.75, 'cp': [6.349, 0.011062, 4.851e-05, -6.484e-08, 2.469e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'acetic acid', 'cas': '64-19-7', 'formula': 'C2H4O2', 'MW': 60.05196, 'Tc': 590.7, 'Pc': 5780000.0, 'omega': 0.4218, 'A': 9.54456, 'B': 1555.12, 'C': -48.5, 'Tmin': 297.58, 'Tmax': 414.97, 'Tb': 391.05, 'cp': [4.375, -0.002397, 6.757e-05, -8.764e-08, 3.478e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'phenol', 'cas': '108-95-2', 'formula': 'C6H6O', 'MW': 94.11124, 'Tc': 694.2, 'Pc': 5930000.0, 'omega': 0.44, 'A': 9.2696, 'B': 1523.42, 'C': -97.75, 'Tmin': 353.0, 'Tmax': 481.62, 'Tb': 454.95, 'cp': [2.582, 0.017501, 8.894e-05, -1.4435e-07, 6.317e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'aniline', 'cas': '62-53-3', 'formula': 'C6H7N', 'MW': 93.12648, 'Tc': 705.0, 'Pc': 5300000.0, 'omega': 0.382, 'A': 9.4087, 'B': 1692.77, 'C': -72.71, 'Tmin': 349.86, 'Tmax': 484.81, 'Tb': 457.25, 'cp': [2.598, 0.019936, 8.438e-05, -1.3368e-07, 5.63e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'CRC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'diethyl ether', 'cas': '60-29-7', 'formula': 'C4H10O', 'MW': 74.1216, 'Tc': 466.7, 'Pc': 3720200.0, 'omega': 0.29, 'A': 9.10962, 'B': 1090.64, 'C': -41.95, 'Tmin': 229.71, 'Tmax': 328.31, 'Tb': 307.604401817, 'cp': [4.612, 0.037492, -1.87e-05, 1.316e-08, -6.98e-12], 'cp_Tmin': 100.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'ethyl acetate', 'cas': '141-78-6', 'formula': 'C4H8O2', 'MW': 88.10512, 'Tc': 523.3, 'Pc': 3870000.0, 'omega': 0.363, 'A': 9.13361, 'B': 1195.13, 'C': -60.68, 'Tmin': 265.5, 'Tmax': 372.51, 'Tb': 350.25, 'cp': [10.228, -0.014948, 0.00013033, -1.5736e-07, 5.999e-11], 'cp_Tmin': 298.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'benzene', 'cas': '71-43-2', 'formula': 'C6H6', 'MW': 78.11184, 'Tc': 562.02, 'Pc': 4907277.0, 'omega': 0.211, 'A': 8.98523, 'B': 1184.24, 'C': -55.578, 'Tmin': 279.64, 'Tmax': 377.06, 'Tb': 353.218780053, 'cp': [3.551, -0.006184, 0.00014365, -1.9807e-07, 8.234e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'toluene', 'cas': '108-88-3', 'formula': 'C7H8', 'MW': 92.13842, 'Tc': 591.75, 'Pc': 4126300.0, 'omega': 0.2657, 'A': 9.05043, 'B': 1327.62, 'C': -55.525, 'Tmin': 286.44, 'Tmax': 409.61, 'Tb': 383.745753146, 'cp': [3.866, 0.003558, 0.00013356, -1.8659e-07, 7.69e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'o-xylene', 'cas': '95-47-6', 'formula': 'C8H10', 'MW': 106.165, 'Tc': 630.259, 'Pc': 3737500.0, 'omega': 0.312, 'A': 9.09789, 'B': 1458.706, 'C': -61.109, 'Tmin': 312.75, 'Tmax': 445.3, 'Tb': 417.521024789, 'cp': [3.289, 0.034144, 4.989e-05, -8.335e-08, 3.338e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'p-xylene', 'cas': '106-42-3', 'formula': 'C8H10', 'MW': 106.165, 'Tc': 616.168, 'Pc': 3531500.0, 'omega': 0.324, 'A': 9.10494, 'B': 1446.832, 'C': -58.523, 'Tmin': 307.81, 'Tmax': 438.88, 'Tb': 411.470471826, 'cp': [4.113, 0.014909, 0.0001181, -1.6724e-07, 6.736e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'ethylbenzene', 'cas': '100-41-4', 'formula': 'C8H10', 'MW': 106.165, 'Tc': 617.12, 'Pc': 3622400.0, 'omega': 0.305, 'A': 9.06861, 'B': 1415.77, 'C': -60.85, 'Tmin': 306.32, 'Tmax': 436.63, 'Tb': 409.314225797, 'cp': [4.544, 0.010578, 0.00013644, -1.9276e-07, 7.885e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'methane', 'cas': '74-82-8', 'formula': 'CH4', 'MW': 16.04246, 'Tc': 190.564, 'Pc': 4599200.0, 'omega': 0.01142, 'A': 8.7687, 'B': 395.744, 'C': -6.469, 'Tmin': 92.64, 'Tmax': 120.59, 'Tb': 111.667205474, 'cp': [4.568, -0.008975, 3.631e-05, -3.407e-08, 1.091e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'ethane', 'cas': '74-84-0', 'formula': 'C2H6', 'MW': 30.06904, 'Tc': 305.322, 'Pc': 4872200.0, 'omega': 0.0995, 'A': 8.95405, 'B': 663.72, 'C': -16.469, 'Tmin': 133.8, 'Tmax': 198.16, 'Tb': 184.568587832, 'cp': [4.178, -0.004427, 5.66e-05, -6.651e-08, 2.487e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'propane', 'cas': '74-98-6', 'formula': 'C3H8', 'MW': 44.09562, 'Tc': 369.89, 'Pc': 4251200.0, 'omega': 0.1521, 'A': 8.92828, 'B': 803.997, 'C': -26.11, 'Tmin': 168.9, 'Tmax': 247.76, 'Tb': 231.03624791, 'cp': [3.847, 0.005131, 6.011e-05, -7.893e-08, 3.079e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'n-butane', 'cas': '106-97-8', 'formula': 'C4H10', 'MW': 58.1222, 'Tc': 425.125, 'Pc': 3796000.0, 'omega': 0.201, 'A': 8.93266, 'B': 935.773, 'C': -34.361, 'Tmin': 200.5, 'Tmax': 292.03, 'Tb': 272.659900526, 'cp': [5.547, 0.005536, 8.057e-05, -1.0571e-07, 4.134e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'isobutane', 'cas': '75-28-5', 'formula': 'C4H10', 'MW': 58.1222, 'Tc': 407.81, 'Pc': 3629000.0, 'omega': 0.184, 'A': 9.00272, 'B': 947.54, 'C': -24.28, 'Tmin': 190.4, 'Tmax': 280.25, 'Tb': 261.401014643, 'cp': [3.351, 0.017883, 5.477e-05, -8.1e-08, 3.243e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'n-pentane', 'cas': '109-66-0', 'formula': 'C5H12', 'MW': 72.14878, 'Tc': 469.7, 'Pc': 3367500.0, 'omega': 0.251, 'A': 8.97786, 'B': 1064.84, 'C': -41.136, 'Tmin': 228.71, 'Tmax': 330.75, 'Tb': 309.20934582, 'cp': [7.554, -0.000368, 0.00011846, -1.4939e-07, 5.753e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'n-hexane', 'cas': '110-54-3', 'formula': 'C6H14', 'MW': 86.17536, 'Tc': 507.82, 'Pc': 3044100.0, 'omega': 0.3, 'A': 9.00139, 'B': 1170.875, 'C': -48.833, 'Tmin': 254.24, 'Tmax': 365.25, 'Tb': 341.865616634, 'cp': [8.831, -0.000166, 0.00014302, -1.8314e-07, 7.124e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'n-heptane', 'cas': '142-82-5', 'formula': 'C7H16', 'MW': 100.20194, 'Tc': 540.2, 'Pc': 2735730.0, 'omega': 0.349, 'A': 9.02023, 'B': 1263.909, 'C': -56.718, 'Tmin': 277.71, 'Tmax': 396.53, 'Tb': 371.550360483, 'cp': [9.634, 0.004156, 0.00015494, -2.0066e-07, 7.77e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'n-octane', 'cas': '111-65-9', 'formula': 'C8H18', 'MW': 114.22852, 'Tc': 568.74, 'Pc': 2483590.0, 'omega': 0.398, 'A': 9.05075, 'B': 1356.36, 'C': -63.515, 'Tmin': 299.42, 'Tmax': 425.23, 'Tb': 398.793755135, 'cp': [10.824, 0.004983, 0.00017751, -2.3137e-07, 8.98e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'n-decane', 'cas': '124-18-5', 'formula': 'C10H22', 'MW': 142.28168, 'Tc': 617.7, 'Pc': 2103000.0, 'omega': 0.4884, 'A': 9.06853, 'B': 1495.17, 'C': -79.292, 'Tmin': 338.53, 'Tmax': 476.15, 'Tb': 447.270229382, 'cp': [13.467, 0.004139, 0.00023127, -3.0477e-07, 1.197e-10], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'cyclohexane', 'cas': '110-82-7', 'formula': 'C6H12', 'MW': 84.15948, 'Tc': 553.6, 'Pc': 4080500.0, 'omega': 0.2096, 'A': 8.93002, 'B': 1182.774, 'C': -52.532, 'Tmin': 282.11, 'Tmax': 378.46, 'Tb': 353.864948368, 'cp': [4.035, -0.004433, 0.00016834, -2.0775e-07, 7.746e-11], 'cp_Tmin': 100.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'ethylene', 'cas': '74-85-1', 'formula': 'C2H4', 'MW': 28.05316, 'Tc': 282.35, 'Pc': 5041800.0, 'omega': 0.0866, 'A': 8.91382, 'B': 596.526, 'C': -16.78, 'Tmin': 123.06, 'Tmax': 181.9, 'Tb': 169.378648434, 'cp': [4.221, -0.008782, 5.795e-05, -6.729e-08, 2.511e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'propylene', 'cas': '115-07-1', 'formula': 'C3H6', 'MW': 42.07974, 'Tc': 364.211, 'Pc': 4555000.0, 'omega': 0.146, 'A': 8.95606, 'B': 789.624, 'C': -25.57, 'Tmin': 165.2, 'Tmax': 241.61, 'Tb': 225.530871246, 'cp': [3.834, 0.003893, 4.688e-05, -6.013e-08, 2.283e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': '1,3-butadiene', 'cas': '106-99-0', 'formula': 'C4H6', 'MW': 54.09044, 'Tc': 425.135, 'Pc': 4305300.0, 'omega': 0.192, 'A': 8.9664, 'B': 927.21, 'C': -34.52, 'Tmin': 198.0, 'Tmax': 287.49, 'Tb': 268.661415208, 'cp': [3.607, 0.005085, 8.253e-05, -1.2371e-07, 5.321e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'chloroform', 'cas': '67-66-3', 'formula': 'CHCl3', 'MW': 119.37764, 'Tc': 536.2, 'Pc': 5330000.0, 'omega': 0.216, 'A': 8.96288, 'B': 1106.904, 'C': -54.598, 'Tmin': 250.1, 'Tmax': 356.89, 'Tb': 334.35, 'cp': [2.389, 0.026218, -3.145e-05, 1.857e-08, -4.23e-12], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'dichloromethane', 'cas': '75-09-2', 'formula': 'CH2Cl2', 'MW': 84.93258, 'Tc': 508.0, 'Pc': 6350000.0, 'omega': 0.2027, 'A': 9.07622, 'B': 1070.07, 'C': -49.91, 'Tmin': 235.2, 'Tmax': 333.36, 'Tb': 312.95, 'cp': [2.71, 0.011561, 3.24e-06, -1.37e-08, 6.62e-12], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'carbon tetrachloride', 'cas': '56-23-5', 'formula': 'CCl4', 'MW': 153.8227, 'Tc': 556.3, 'Pc': 4540000.0, 'omega': 0.194, 'A': 9.10445, 'B': 1265.632, 'C': -41.002, 'Tmin': 259.0, 'Tmax': 373.76, 'Tb': 349.85, 'cp': [2.518, 0.041882, -7.16e-05, 5.739e-08, -1.756e-11], 'cp_Tmin': 200.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'IUPAC', 'Pc': 'IUPAC', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_ORG', 'cp': 'POLING_CP'}},
    {'name': 'ammonia', 'cas': '7664-41-7', 'formula': 'H3N', 'MW': 17.03052, 'Tc': 405.56, 'Pc': 11363400.0, 'omega': 0.256, 'A': 9.4854, 'B': 926.132, 'C': -32.98, 'Tmin': 193.03, 'Tmax': 254.31, 'Tb': 239.83431862, 'cp': [4.238, -0.004215, 2.041e-05, -2.126e-08, 7.61e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'nitrogen', 'cas': '7727-37-9', 'formula': 'N2', 'MW': 28.0134, 'Tc': 126.192, 'Pc': 3395800.0, 'omega': 0.0372, 'A': 8.61947, 'B': 255.68, 'C': -6.6, 'Tmin': 60.81, 'Tmax': 83.65, 'Tb': 77.3549950205, 'cp': [3.539, -0.000261, 7e-08, 1.57e-09, -9.9e-13], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'oxygen', 'cas': '7782-44-7', 'formula': 'O2', 'MW': 31.9988, 'Tc': 154.581, 'Pc': 5043000.0, 'omega': 0.0222, 'A': 8.81634, 'B': 319.013, 'C': -6.45, 'Tmin': 64.29, 'Tmax': 97.2, 'Tb': 90.1878078805, 'cp': [3.63, -0.001794, 6.58e-06, -6e-09, 1.79e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'hydrogen sulfide', 'cas': '7783-06-4', 'formula': 'H2S', 'MW': 34.08088, 'Tc': 373.1, 'Pc': 9000000.0, 'omega': 0.1005, 'A': 9.22882, 'B': 806.933, 'C': -21.76, 'Tmin': 185.51, 'Tmax': 227.2, 'Tb': 212.854883148, 'cp': [4.266, -0.003438, 1.319e-05, -1.331e-08, 4.88e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'sulfur dioxide', 'cas': '7446-09-5', 'formula': 'O2S', 'MW': 64.0638, 'Tc': 430.64, 'Pc': 7886600.0, 'omega': 0.256, 'A': 9.4072, 'B': 999.9, 'C': -35.96, 'Tmin': 199.71, 'Tmax': 279.47, 'Tb': 263.137015354, 'cp': [4.417, -0.002234, 2.344e-05, -3.271e-08, 1.393e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'carbon dioxide', 'cas': '124-38-9', 'formula': 'CO2', 'MW': 44.0095, 'Tc': 304.1282, 'Pc': 7377300.0, 'omega': 0.22394, 'A': None, 'B': None, 'C': None, 'Tmin': None, 'Tmax': None, 'Tb': None, 'cp': [3.259, 0.001356, 1.502e-05, -2.374e-08, 1.056e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': None, 'Tb': None, 'cp': 'POLING_CP'}},
    {'name': 'carbon monoxide', 'cas': '630-08-0', 'formula': 'CO', 'MW': 28.0101, 'Tc': 132.86, 'Pc': 3494000.0, 'omega': 0.0497, 'A': 8.81912, 'B': 291.743, 'C': -5.154, 'Tmin': 69.73, 'Tmax': 88.08, 'Tb': 81.6381829183, 'cp': [3.912, -0.003913, 1.182e-05, -1.3e-08, 5.15e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'hydrogen', 'cas': '1333-74-0', 'formula': 'H2', 'MW': 2.01588, 'Tc': 33.145, 'Pc': 1296400.0, 'omega': -0.219, 'A': 7.93954, 'B': 66.7954, 'C': 2.5, 'Tmin': 10.25, 'Tmax': 22.82, 'Tb': 20.3689085101, 'cp': [2.883, 0.003681, -7.72e-06, 6.92e-09, -2.13e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'chlorine', 'cas': '7782-50-5', 'formula': 'Cl2', 'MW': 70.906, 'Tc': 416.8654, 'Pc': 7642400.0, 'omega': 0.07, 'A': 9.0628, 'B': 861.34, 'C': -26.82, 'Tmin': 176.31, 'Tmax': 255.79, 'Tb': 239.197637887, 'cp': [3.056, 0.0053708, -8.098e-06, 5.693e-09, -1.5256e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'hydrogen chloride', 'cas': '7647-01-0', 'formula': 'ClH', 'MW': 36.46094, 'Tc': 324.68, 'Pc': 8313500.0, 'omega': 0.129, 'A': 9.2949, 'B': 745.78, 'C': -14.27, 'Tmin': 159.97, 'Tmax': 201.0, 'Tb': 188.172607605, 'cp': [3.827, -0.002936, 8.79e-06, -1.031e-08, 4.39e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'argon', 'cas': '7440-37-1', 'formula': 'Ar', 'MW': 39.948, 'Tc': 150.687, 'Pc': 4863000.0, 'omega': -0.00219, 'A': 8.74141, 'B': 304.227, 'C': -5.83, 'Tmin': 82.59, 'Tmax': 94.26, 'Tb': 87.3021362362, 'cp': [2.5, 0.0, 0.0, 0.0, 0.0], 'cp_Tmin': None, 'cp_Tmax': None, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'helium', 'cas': '7440-59-7', 'formula': 'He', 'MW': 4.0026, 'Tc': 5.1953, 'Pc': 228320.0, 'omega': -0.3836, 'A': 6.6836, 'B': 8.1548, 'C': 0.56, 'Tmin': 1.85, 'Tmax': 5.34, 'Tb': 4.22380677084, 'cp': [2.5, 0.0, 0.0, 0.0, 0.0], 'cp_Tmin': None, 'cp_Tmax': None, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'nitrous oxide', 'cas': '10024-97-2', 'formula': 'N2O', 'MW': 44.0128, 'Tc': 309.52, 'Pc': 7245000.0, 'omega': 0.162, 'A': 9.12884, 'B': 654.26, 'C': -25.99, 'Tmin': 180.82, 'Tmax': 196.91, 'Tb': 184.683943645, 'cp': [3.165, 0.003401, 9.89e-06, -1.88e-08, 8.9e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'HEOS', 'Pc': 'HEOS', 'omega': 'HEOS', 'antoine': 'POLING', 'Tb': 'HEOS', 'cp': 'POLING_CP'}},
    {'name': 'nitric oxide', 'cas': '10102-43-9', 'formula': 'NO', 'MW': 30.0061, 'Tc': 180.0, 'Pc': 6484800.0, 'omega': 0.588, 'A': 10.8679, 'B': 682.9386, 'C': -4.88, 'Tmin': 106.94, 'Tmax': 127.56, 'Tb': 121.41, 'cp': [4.534, -0.007644, 2.066e-05, -2.156e-08, 8.06e-12], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'MATTHEWS', 'Pc': 'MATTHEWS', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_INORG', 'cp': 'POLING_CP'}},
    {'name': 'sulfur trioxide', 'cas': '7446-11-9', 'formula': 'O3S', 'MW': 80.0632, 'Tc': 491.0, 'Pc': 8207325.0, 'omega': 0.4121, 'A': 11.17575, 'B': 1735.31, 'C': -36.65, 'Tmin': 284.5, 'Tmax': 332.04, 'Tb': 317.65, 'cp': [3.426, 0.006479, 1.691e-05, -3.356e-08, 1.59e-11], 'cp_Tmin': 50.0, 'cp_Tmax': 1000.0, 'src': {'MW': 'FORMULA', 'Tc': 'MATTHEWS', 'Pc': 'MATTHEWS', 'omega': 'PSRK', 'antoine': 'POLING', 'Tb': 'CRC_INORG', 'cp': 'POLING_CP'}},
)

WATER_COLUMNS = ('T_C', 'rho', 'cp', 'mu', 'k', 'Pr')
WATER_1ATM: tuple[tuple[float, ...], ...] = (
    (0.0, 999.843, 4219.44, 0.00179176, 0.55565, 13.6061),
    (10.0, 999.702, 4195.16, 0.0013059, 0.578777, 9.46557),
    (20.0, 998.207, 4184.05, 0.0010016, 0.598012, 7.00776),
    (25.0, 997.048, 4181.31, 0.000890022, 0.606516, 6.1358),
    (30.0, 995.649, 4179.82, 0.000797222, 0.614392, 5.42364),
    (40.0, 992.216, 4179.41, 0.000652729, 0.628486, 4.34063),
    (50.0, 988.035, 4181.34, 0.000546516, 0.640621, 3.56712),
    (60.0, 983.196, 4184.95, 0.000466035, 0.651, 2.99591),
    (70.0, 977.765, 4190.07, 0.000403548, 0.659758, 2.5629),
    (80.0, 971.79, 4196.75, 0.000354051, 0.666994, 2.2277),
    (90.0, 965.31, 4205.21, 0.000314175, 0.672789, 1.96372),
    (100.0, 958.349, 4215.67, 0.000281582, 0.677211, 1.75286),
)

FULLER_ATOMS: dict[str, float] = {'C': 15.9, 'H': 2.31, 'O': 6.11, 'N': 4.54, 'Cl': 21.0, 'S': 22.9}
FULLER_RINGS: dict[str, float] = {'aromatic ring': -18.3, 'heterocyclic ring': -18.3}
FULLER_MOLECULES: dict[str, float] = {
    'He': 2.67,
    'Ne': 5.98,
    'Ar': 16.2,
    'Kr': 24.5,
    'Xe': 32.7,
    'H2': 6.12,
    'D2': 6.84,
    'N2': 18.5,
    'O2': 16.3,
    'air': 19.7,
    'CO': 18.0,
    'CO2': 26.9,
    'N2O': 35.9,
    'NH3': 20.7,
    'H2O': 13.1,
    'SF6': 71.3,
    'Cl2': 38.4,
    'Br2': 69.0,
    'SO2': 41.8,
}
# fmt: on
