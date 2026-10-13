"""Compound table checks. Literature values are independent of the export: normal boiling
points and critical temperatures from the CRC Handbook (rounded), molar masses from
IUPAC atomic weights (current conventional values, so MW within 0.005)."""

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


@pytest.mark.parametrize(
    "name,nbp",
    [
        ("water", 373.12),
        ("methanol", 337.8),
        ("ethanol", 351.4),
        ("acetone", 329.2),
        ("benzene", 353.2),
        ("toluene", 383.8),
        ("n-hexane", 341.9),
        ("cyclohexane", 353.9),
        ("nitrogen", 77.36),
        ("oxygen", 90.19),
        ("ammonia", 239.8),
    ],
)
def test_antoine_reproduces_normal_boiling_points(name: str, nbp: float) -> None:
    assert antoine_nbp(by_name(name)) == pytest.approx(nbp, abs=0.5)


@pytest.mark.parametrize(
    "name,tc,mw",
    [("water", 647.1, 18.015), ("benzene", 562.0, 78.114), ("ethanol", 514.0, 46.069)],
)
def test_critical_temperature_and_molar_mass(name: str, tc: float, mw: float) -> None:
    r = by_name(name)
    assert r["Tc"] == pytest.approx(tc, rel=1e-3)
    assert r["MW"] == pytest.approx(mw, abs=5e-3)  # 2007 vs current atomic weights


def test_export_reproduces_file() -> None:
    pytest.importorskip("chemicals", minversion="1.5.2")
    spec = importlib.util.spec_from_file_location(
        "export_compounds", ROOT / "tools" / "export_compounds.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = (ROOT / "templates" / "_compounds.py").read_text(encoding="utf-8")
    assert mod.render(mod.rows()) == text
