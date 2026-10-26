"""Export the ChemLab compound table once from the `chemicals` library (MIT licence).

    pip install chemicals==1.5.2
    python chemlab/tools/export_compounds.py      # rewrites chemlab/templates/_compounds.py

`chemicals` is a one-off export tool, not a dependency: the templates (and the browser
sandbox) only read the generated `_compounds.py`. Every value keeps the name of the data
table it came from; SOURCES gives the full reference. Re-running with the same version
must reproduce the file byte for byte (tested when `chemicals` is installed). The data
block is marked `fmt: off` so ruff keeps one compound per line.
"""

import statistics
from pathlib import Path

import chemicals
from chemicals import (
    Pc,
    Pc_methods,
    Tb,
    Tb_methods,
    Tc,
    Tc_methods,
    omega,
    omega_methods,
)
from chemicals.heat_capacity import Cp_data_Poling
from chemicals.iapws import iapws95_properties, iapws95_Psat, iapws95_rho
from chemicals.identifiers import search_chemical
from chemicals.thermal_conductivity import k_IAPWS
from chemicals.vapor_pressure import Psat_data_AntoinePoling
from chemicals.viscosity import mu_IAPWS

VERSION = "1.5.2"
OUT = Path(__file__).resolve().parents[1] / "templates" / "_compounds.py"

# Engineering-course compounds with Poling Cp data (50); 40 have Poling Antoine constants
NAMES = [
    "water", "methanol", "ethanol", "1-propanol", "2-propanol", "1-butanol",
    "acetone", "methyl ethyl ketone", "acetic acid", "phenol", "aniline",
    "diethyl ether", "ethyl acetate", "benzene", "toluene", "o-xylene", "p-xylene",
    "ethylbenzene", "methane", "ethane", "propane", "n-butane", "isobutane",
    "n-pentane", "n-hexane", "n-heptane", "n-octane", "n-decane", "cyclohexane",
    "ethylene", "propylene", "1,3-butadiene", "chloroform", "dichloromethane",
    "carbon tetrachloride", "ammonia", "nitrogen", "oxygen", "hydrogen sulfide",
    "sulfur dioxide", "carbon dioxide", "carbon monoxide", "hydrogen", "chlorine",
    "hydrogen chloride", "argon", "helium", "nitrous oxide", "nitric oxide",
    "sulfur trioxide",
]  # fmt: skip
# Data tables only (estimation methods such as Joback are never used). A value is taken
# from the first table in PREFER that agrees with the median of all tables within TOL;
# this rejects single-table errors (chemicals 1.5.2's IUPAC row for cyclohexane holds
# methylcyclopentane's constants, its n-decane Tc is 6 K low).
TABLES = (
    "HEOS",
    "IUPAC",
    "MATTHEWS",
    "CRC",
    "WEBBOOK",
    "PSRK",
    "PD",
    "PINAMARTINES",
    "YAWS",
)
PREFER = ("HEOS", "IUPAC", "MATTHEWS", "CRC", "WEBBOOK", "PSRK")
# agreement with the median: Tc and Pc relative, omega absolute (it is near 0 for
# methane; acetic acid, a dimerising acid, has 0.42 and 0.47 in different tables)
TOL = {"Tc": 0.005, "Pc": 0.03, "omega": 0.03, "Tb": 0.005}
# normal boiling point tables (JOBACK, an estimation method, and WIKIDATA are not used)
TB_TABLES = ("HEOS", "CRC_ORG", "CRC_INORG", "WEBBOOK", "YAWS", "COMMON_CHEMISTRY")
TB_PREFER = ("HEOS", "CRC_ORG", "CRC_INORG", "WEBBOOK")
# Liquid water at 1 atm (saturated liquid at 100 C: 1 atm is just below Psat there)
WATER_T_C = (0, 10, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100)
P_ATM = 101325.0
# Poling, Prausnitz, O'Connell, 5th ed., Table 11-1 (Fuller et al. atomic and simple
# molecule diffusion volumes, cm3/mol); typed in by hand, not from chemicals
FULLER_ATOMS = {"C": 15.9, "H": 2.31, "O": 6.11, "N": 4.54, "Cl": 21.0, "S": 22.9}
FULLER_RINGS = {"aromatic ring": -18.3, "heterocyclic ring": -18.3}
FULLER_MOLECULES = {
    "He": 2.67, "Ne": 5.98, "Ar": 16.2, "Kr": 24.5, "Xe": 32.7, "H2": 6.12, "D2": 6.84,
    "N2": 18.5, "O2": 16.3, "air": 19.7, "CO": 18.0, "CO2": 26.9, "N2O": 35.9,
    "NH3": 20.7, "H2O": 13.1, "SF6": 71.3, "Cl2": 38.4, "Br2": 69.0, "SO2": 41.8,
}  # fmt: skip
SOURCES = {
    "IUPAC": "IUPAC critically evaluated series 'Vapor-Liquid Critical Properties of"
    " Elements and Compounds' parts 1-12, J. Chem. Eng. Data (1995-2015)",
    "MATTHEWS": "Mathews, Critical Constants of Inorganic Substances, Chem. Rev. 72"
    " (1972) 71-100",
    "CRC": "Haynes, Bruno, Lide, CRC Handbook of Chemistry and Physics, 95th ed. (2014)",
    "PSRK": "Horstmann et al., PSRK Group Contribution Equation of State revision IV,"
    " Fluid Phase Equilib. 227 (2005) 157-164 (experimental and estimated values)",
    "PD": "Passut, Danner, Acentric Factor, Ind. Eng. Chem. Process Des. Dev. 12"
    " (1973) 365-368",
    "YAWS": "Yaws, Thermophysical Properties of Chemicals and Hydrocarbons, 2nd ed."
    " (2014)",
    "POLING": "Poling, Prausnitz, O'Connell, The Properties of Gases and Liquids, 5th"
    " ed. (2000), Antoine constants converted to log10(P/Pa) = A - B/(T/K + C)",
    "HEOS": "reference equations of state as in NIST REFPROP (critical point and"
    " acentric factor of the equation)",
    "WEBBOOK": "NIST Chemistry WebBook, SRD 69",
    "CRC_ORG": "Haynes, Bruno, Lide, CRC Handbook of Chemistry and Physics, 95th ed."
    " (2014), physical constants of organic compounds",
    "CRC_INORG": "Haynes, Bruno, Lide, CRC Handbook of Chemistry and Physics, 95th ed."
    " (2014), physical constants of inorganic compounds",
    "COMMON_CHEMISTRY": "CAS Common Chemistry, commonchemistry.cas.org",
    "POLING_CP": "Poling, Prausnitz, O'Connell, The Properties of Gases and Liquids, 5th"
    " ed. (2000), ideal-gas heat capacity polynomial Cp/R = a0 + a1 T + a2 T^2 + a3 T^3"
    " + a4 T^4",
    "IAPWS": "IAPWS-95 (density, Cp), IAPWS 2008 viscosity release, IAPWS 2011"
    " thermal conductivity release, as implemented in chemicals",
    "FORMULA": "molar mass from the formula, IUPAC 2007 atomic weights as tabulated"
    " in chemicals",
}


def consensus(
    fn, methods_fn, prop: str, cas: str, tables=TABLES, prefer=PREFER
) -> tuple[float | None, str | None]:
    have = {m: float(fn(cas, method=m)) for m in methods_fn(cas) if m in tables}
    if len(have) < 2:  # cannot cross-check: leave the field empty
        return None, None
    med = statistics.median(have.values())
    for m in (m for m in prefer if m in have):
        off = abs(have[m] - med) if prop == "omega" else abs(have[m] / med - 1)
        if off <= TOL[prop]:
            return have[m], m
    raise SystemExit(f"{cas} {prop}: no preferred table agrees with the median {med}")


def rows() -> list[dict]:
    out = []
    for name in NAMES:
        cas = chemicals.CAS_from_any(name)
        meta = search_chemical(cas)
        ant = Psat_data_AntoinePoling.loc[cas] if cas in Psat_data_AntoinePoling.index else None
        tc, tc_src = consensus(Tc, Tc_methods, "Tc", cas)
        pc, pc_src = consensus(Pc, Pc_methods, "Pc", cas)
        om, om_src = consensus(omega, omega_methods, "omega", cas)
        tb, tb_src = consensus(Tb, Tb_methods, "Tb", cas, TB_TABLES, TB_PREFER)
        cp = Cp_data_Poling.loc[cas]
        out.append(
            {
                "name": name,
                "cas": cas,
                "formula": meta.formula,
                "MW": round(float(meta.MW), 5),
                "Tc": tc,
                "Pc": pc,
                "omega": om,
                "A": None if ant is None else float(ant.A),
                "B": None if ant is None else float(ant.B),
                "C": None if ant is None else float(ant.C),
                "Tmin": None if ant is None else float(ant.Tmin),
                "Tmax": None if ant is None else float(ant.Tmax),
                "Tb": tb,
                "cp": [float(cp[f"a{i}"]) for i in range(5)],
                "cp_Tmin": float(cp.Tmin) if cp.Tmin == cp.Tmin else None,  # NaN: no range
                "cp_Tmax": float(cp.Tmax) if cp.Tmax == cp.Tmax else None,
                "src": {
                    "MW": "FORMULA",
                    "Tc": tc_src,
                    "Pc": pc_src,
                    "omega": om_src,
                    "antoine": None if ant is None else "POLING",
                    "Tb": tb_src,
                    "cp": "POLING_CP",
                },
            }
        )
    return out


def water_rows() -> list[tuple[float, ...]]:
    out = []
    for t_c in WATER_T_C:
        t = 273.15 + t_c
        p = max(P_ATM, iapws95_Psat(t))
        rho = iapws95_rho(t, p)
        _, _, _, _, cv, cp, _, _, _, _, drho_dp = iapws95_properties(t, p)
        mu = mu_IAPWS(t, rho, drho_dp)
        k = k_IAPWS(t, rho, cp, cv, mu, drho_dp)
        vals = (rho, cp, mu, k, cp * mu / k)
        out.append((float(t_c), *(float(f"{v:.6g}") for v in vals)))
    return out


def render(data: list[dict]) -> str:
    used = {s for row in data for s in row["src"].values() if s} | {"IAPWS"}
    lines = [
        '"""Compound data for ChemLab templates. GENERATED, do not edit by hand:',
        f"run chemlab/tools/export_compounds.py (chemicals {VERSION}).",
        "",
        "A, B, C, Tmin, Tmax (and src antoine) are None when there is no Poling Antoine row; Tb,",
        "Tc, Pc, omega are None (src None) when fewer than 2 data tables exist.",
        "Units: MW kg/kmol, Tc K, Pc Pa, omega -, Tb K (normal boiling point), Antoine",
        "log10(Psat/Pa) = A - B/(T + C) with T in K, valid for Tmin <= T <= Tmax.",
        '"cp" = [a0..a4], ideal-gas Cp/R = a0 + a1 T + a2 T^2 + a3 T^3 + a4 T^4 (T in K,',
        "Cp in J/mol/K = R * that, R = 8.314462618 J/mol/K), valid cp_Tmin <= T <= cp_Tmax.",
        '"src" names the table each value came from (see SOURCES): the first preferred',
        "table that agrees with the median of all data tables in chemicals (see the",
        "exporter). The omega, Tc/Pc, Tb and Antoine values of a row can come from",
        "different tables.",
        "",
        "WATER_1ATM: liquid water at 1 atm, rows of WATER_COLUMNS (T_C degC, rho kg/m3,",
        "cp J/kg/K, mu Pa s, k W/m/K, Pr -); the 100 degC row is saturated liquid at",
        "101.42 kPa (1 atm is just below its vapour pressure). Source IAPWS (see SOURCES).",
        "",
        "FULLER_*: diffusion volumes in cm3/mol for the Fuller-Schettler-Giddings method,",
        "Poling, Prausnitz, O'Connell, The Properties of Gases and Liquids, 5th ed.,",
        'Table 11-1 (atoms, rings, simple molecules)."""',
        "",
        "from typing import Any",
        "",
        "# fmt: off",
        "SOURCES: dict[str, str] = {",
        *(f"    {k!r}: {v!r}," for k, v in SOURCES.items() if k in used),
        "}",
        "",
        "COMPOUNDS: tuple[dict[str, Any], ...] = (",
        *(f"    {row!r}," for row in data),
        ")",
        "",
        f"WATER_COLUMNS = {('T_C', 'rho', 'cp', 'mu', 'k', 'Pr')!r}",
        "WATER_1ATM: tuple[tuple[float, ...], ...] = (",
        *(f"    {row!r}," for row in water_rows()),
        ")",
        "",
        f"FULLER_ATOMS: dict[str, float] = {FULLER_ATOMS!r}",
        f"FULLER_RINGS: dict[str, float] = {FULLER_RINGS!r}",
        "FULLER_MOLECULES: dict[str, float] = {",
        *(f"    {k!r}: {v!r}," for k, v in FULLER_MOLECULES.items()),
        "}",
        "# fmt: on",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    assert chemicals.__version__ == VERSION, chemicals.__version__
    OUT.write_text(render(rows()), encoding="utf-8")
    print(f"wrote {OUT}")
