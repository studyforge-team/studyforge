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
from chemicals import Pc, Pc_methods, Tc, Tc_methods, omega, omega_methods
from chemicals.identifiers import search_chemical
from chemicals.vapor_pressure import Psat_data_AntoinePoling

VERSION = "1.5.2"
OUT = Path(__file__).resolve().parents[1] / "templates" / "_compounds.py"

# Engineering-course compounds that have Poling Antoine constants (40)
NAMES = [
    "water", "methanol", "ethanol", "1-propanol", "2-propanol", "1-butanol",
    "acetone", "methyl ethyl ketone", "acetic acid", "phenol", "aniline",
    "diethyl ether", "ethyl acetate", "benzene", "toluene", "o-xylene", "p-xylene",
    "ethylbenzene", "methane", "ethane", "propane", "n-butane", "isobutane",
    "n-pentane", "n-hexane", "n-heptane", "n-octane", "n-decane", "cyclohexane",
    "ethylene", "propylene", "1,3-butadiene", "chloroform", "dichloromethane",
    "carbon tetrachloride", "ammonia", "nitrogen", "oxygen", "hydrogen sulfide",
    "sulfur dioxide",
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
TOL = {"Tc": 0.005, "Pc": 0.03, "omega": 0.03}
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
    "FORMULA": "molar mass from the formula, IUPAC 2007 atomic weights as tabulated"
    " in chemicals",
}


def consensus(fn, methods_fn, prop: str, cas: str) -> tuple[float, str]:
    have = {m: float(fn(cas, method=m)) for m in methods_fn(cas) if m in TABLES}
    if len(have) < 2:
        raise SystemExit(f"{cas} {prop}: fewer than 2 data tables, cannot cross-check")
    med = statistics.median(have.values())
    for m in (m for m in PREFER if m in have):
        off = abs(have[m] - med) if prop == "omega" else abs(have[m] / med - 1)
        if off <= TOL[prop]:
            return have[m], m
    raise SystemExit(f"{cas} {prop}: no preferred table agrees with the median {med}")


def rows() -> list[dict]:
    out = []
    for name in NAMES:
        cas = chemicals.CAS_from_any(name)
        meta = search_chemical(cas)
        ant = Psat_data_AntoinePoling.loc[cas]
        tc, tc_src = consensus(Tc, Tc_methods, "Tc", cas)
        pc, pc_src = consensus(Pc, Pc_methods, "Pc", cas)
        om, om_src = consensus(omega, omega_methods, "omega", cas)
        out.append(
            {
                "name": name,
                "cas": cas,
                "formula": meta.formula,
                "MW": round(float(meta.MW), 5),
                "Tc": tc,
                "Pc": pc,
                "omega": om,
                "A": float(ant.A),
                "B": float(ant.B),
                "C": float(ant.C),
                "Tmin": float(ant.Tmin),
                "Tmax": float(ant.Tmax),
                "src": {
                    "MW": "FORMULA",
                    "Tc": tc_src,
                    "Pc": pc_src,
                    "omega": om_src,
                    "antoine": "POLING",
                },
            }
        )
    return out


def render(data: list[dict]) -> str:
    used = {s for row in data for s in row["src"].values()}
    lines = [
        '"""Compound data for ChemLab templates. GENERATED, do not edit by hand:',
        f"run chemlab/tools/export_compounds.py (chemicals {VERSION}).",
        "",
        "Units: MW kg/kmol, Tc K, Pc Pa, omega -, Antoine log10(Psat/Pa) = A - B/(T + C)",
        'with T in K, valid for Tmin <= T <= Tmax. "src" names the table each value',
        "came from (see SOURCES): the first preferred table that agrees with the",
        "median of all data tables in chemicals (see the exporter). The omega, Tc/Pc and",
        'Antoine values of a row can come from different tables."""',
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
        "# fmt: on",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    assert chemicals.__version__ == VERSION, chemicals.__version__
    OUT.write_text(render(rows()), encoding="utf-8")
    print(f"wrote {OUT}")
