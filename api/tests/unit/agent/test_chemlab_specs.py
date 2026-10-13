"""CH3 with every ChemLab template: the generated SPEC file is in sync with the
templates, every canonical unit is convertible, and picks run end to end (the code is
executed here with our own chemlab package, standing in for the browser worker)."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from app.agent.chemlab_pick import (
    _CONVERSIONS,
    RATE_UNIT,
    SPECS_PATH,
    Pick,
    Quantity,
    build_code,
    load_template_specs,
    validate_pick,
)

ROOT = Path(__file__).resolve().parents[4]


def exporter() -> Any:
    spec = importlib.util.spec_from_file_location(
        "export_specs", ROOT / "chemlab" / "tools" / "export_specs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_pick(template: str, inputs: dict[str, tuple[float, str]]) -> dict[str, Any]:
    pick = Pick(
        template=template,
        inputs={k: Quantity(value=v, unit=u) for k, (v, u) in inputs.items()},
    )
    code = build_code(template, validate_pick(pick, load_template_specs()))
    ns: dict[str, Any] = {}
    exec(code, ns)  # noqa: S102 - test only, our own template code
    result: dict[str, Any] = ns["result"]
    return result


def test_specs_file_in_sync_with_templates() -> None:
    text = SPECS_PATH.read_text(encoding="utf-8")
    assert text == exporter().render(), "run: python chemlab/tools/export_specs.py"


def test_every_template_is_listed() -> None:
    files = {p.stem for p in (ROOT / "chemlab" / "templates").glob("[!_]*.py")}
    assert set(load_template_specs()) == files


def test_every_canonical_unit_is_convertible() -> None:
    for tname, spec in load_template_specs().items():
        for iname, s in spec.items():
            assert s["unit"] == RATE_UNIT or s["unit"] in _CONVERSIONS, (tname, iname)


@pytest.mark.parametrize("template", sorted(load_template_specs()))
def test_defaults_run_end_to_end(template: str) -> None:
    spec = load_template_specs()[template]
    r = run_pick(template, {k: (s["default"], s["unit"]) for k, s in spec.items()})
    assert r["ok"], r["errors"]


def test_hx_golden_p1_05_in_question_units() -> None:
    # hot oil 2.0 kg/s, cp 2.1 kJ/(kg K), 160 -> 100 C; water 9000 kg/h, cp 4.18, 20 C
    r = run_pick(
        "hx",
        {
            "mh": (2.0, "kg/s"),
            "cph": (2.1, "kJ/(kg K)"),
            "Th_in": (160, "°C"),
            "Th_out": (100, "°C"),
            "mc": (9000, "kg/h"),
            "cpc": (4.18, "kJ/(kg K)"),
            "Tc_in": (20, "°C"),
            "U": (0.35, "kW/(m^2 K)"),
        },
    )
    assert r["outputs"]["A_counter"]["value"] == pytest.approx(7.43518, rel=1e-5)
