"""Compound table checks against an independent reference table (below) for all 40
compounds, and molar masses from current IUPAC atomic weights. The byte-for-byte export
check runs only where chemicals 1.5.2 is installed (not in CI); the reference table is
what guards the data in CI."""

import importlib.util
import math
from pathlib import Path

import pytest
from chemlab._compounds import COMPOUNDS, SOURCES

ROOT = Path(__file__).resolve().parents[1]
P_ATM = 101325.0


def by_name(name: str) -> dict:
    return next(r for r in COMPOUNDS if r["name"] == name)


def antoine_nbp(r: dict) -> float:
    return r["B"] / (r["A"] - math.log10(P_ATM)) - r["C"]


def test_forty_unique_compounds_with_sources() -> None:
    assert len(COMPOUNDS) == 40
    assert len({r["name"] for r in COMPOUNDS}) == 40
    assert len({r["cas"] for r in COMPOUNDS}) == 40
    for r in COMPOUNDS:
        assert set(r["src"]) == {"MW", "Tc", "Pc", "omega", "antoine"}
        assert all(s in SOURCES for s in r["src"].values()), r["name"]


def test_values_physical() -> None:
    for r in COMPOUNDS:
        assert 2 < r["MW"] < 200 and 50 < r["Tc"] < 800, r["name"]
        assert 1e6 < r["Pc"] < 3e7 and -0.5 < r["omega"] < 1.5, r["name"]
        assert r["Tmin"] < r["Tmax"] < r["Tc"], r["name"]
        assert r["Tmin"] + r["C"] > 0, r["name"]  # Antoine defined over its range
        assert r["Tmin"] < antoine_nbp(r) < r["Tc"], r["name"]


# Independent reference (not the table the export picked from): CRC Handbook 95th ed.
# normal boiling point and, for organics, critical constants; PSRK (Horstmann et al.
# 2005) critical constants for the six inorganics; as tabulated in chemicals 1.5.2.
# name: (Tb K, Tc K, Pc MPa)
REF = {
    "water": (373.12, 647.3, 22.048),
    "methanol": (337.65, 512.7, 8.01),
    "ethanol": (351.39, 515.0, 6.25),
    "1-propanol": (370.19, 536.8, 5.1),
    "2-propanol": (355.36, 508.3, 4.7),
    "1-butanol": (390.75, 563.0, 4.43),
    "acetone": (329.23, 508.1, 4.7),
    "methyl ethyl ketone": (352.75, 537.0, 4.18),
    "acetic acid": (391.05, 593.0, 5.79),
    "phenol": (454.95, 694.3, 5.5),
    "aniline": (457.25, 704.0, 5.3),
    "diethyl ether": (307.55, 466.8, 3.64),
    "ethyl acetate": (350.25, 523.27, 3.88),
    "benzene": (353.23, 562.0, 4.9),
    "toluene": (383.75, 591.9, 4.13),
    "o-xylene": (417.55, 630.26, 3.74),
    "p-xylene": (411.45, 616.17, 3.55),
    "ethylbenzene": (409.35, 617.1, 3.61),
    "methane": (111.65, 190.56, 4.6),
    "ethane": (184.55, 305.36, 4.88),
    "propane": (231.04, 369.9, 4.25),
    "n-butane": (272.65, 425.2, 3.79),
    "isobutane": (261.45, 407.84, 3.64),
    "n-pentane": (309.21, 469.7, 3.37),
    "n-hexane": (341.87, 507.5, 3.03),
    "n-heptane": (371.53, 540.1, 2.74),
    "n-octane": (398.77, 568.7, 2.48),
    "n-decane": (447.25, 618.1, 2.1),
    "cyclohexane": (353.85, 553.4, 4.07),
    "ethylene": (169.35, 282.35, 5.06),
    "propylene": (225.55, 364.9, 4.59),
    "1,3-butadiene": (268.55, 425.0, 4.35),
    "chloroform": (334.35, 536.0, 5.5),
    "dichloromethane": (312.95, 508.0, 6.35),
    "carbon tetrachloride": (349.85, 556.5, 4.57),
    "ammonia": (239.82, 405.6, 11.277),
    "nitrogen": (77.36, 126.2, 3.394),
    "oxygen": (90.19, 154.6, 5.046),
    "hydrogen sulfide": (213.6, 372.8, 8.937),
    "sulfur dioxide": (263.1, 430.8, 7.883),
}


def test_reference_covers_every_compound() -> None:
    assert set(REF) == {r["name"] for r in COMPOUNDS}


@pytest.mark.parametrize("name", list(REF))
def test_against_independent_reference(name: str) -> None:
    r, (tb, tc, pc) = by_name(name), REF[name]
    nbp = antoine_nbp(r)
    assert nbp == pytest.approx(tb, abs=1.0)  # Antoine reproduces the boiling point
    assert r["Tmin"] <= nbp <= r["Tmax"]
    # 0.8 % catches the two bad upstream rows (cyclohexane 3.7 % off, n-decane 1.0 %)
    assert r["Tc"] == pytest.approx(tc, rel=0.008)
    # Pc tables spread more (phenol: CRC 5.50, others 5.93-6.13 MPa)
    assert r["Pc"] / 1e6 == pytest.approx(pc, rel=0.08)


@pytest.mark.parametrize(
    "name,mw", [("water", 18.015), ("benzene", 78.114), ("ammonia", 17.031)]
)
def test_molar_mass(name: str, mw: float) -> None:
    assert by_name(name)["MW"] == pytest.approx(mw, abs=5e-3)  # 2007 vs current weights


def test_export_reproduces_file() -> None:
    chemicals = pytest.importorskip("chemicals")
    if chemicals.__version__ != "1.5.2":
        pytest.skip("the table was exported with chemicals 1.5.2")
    spec = importlib.util.spec_from_file_location(
        "export_compounds", ROOT / "tools" / "export_compounds.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = (ROOT / "templates" / "_compounds.py").read_text(encoding="utf-8")
    assert mod.render(mod.rows()) == text
