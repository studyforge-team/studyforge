"""Shared input/output format for every ChemLab template (frozen with CH1a).

Every template module exposes:
    SPEC: dict[str, InputSpec]   single source for sliders, validation and CH3
    run(inputs: dict, series: bool = True) -> dict

run() returns (always JSON-safe: plain floats/ints/bools/str, no NaN or inf):
    {template, version, ok, errors: [{code, message, field}], warnings: [str],
     inputs: {name: {value, unit}}, outputs: {name: {value, unit}},
     steady_states: [...], n_steady_states,
     series: {name: {x, y, x_unit, y_unit}}, geometry: {...}}
Templates import only numpy and scipy (the sandbox loads packages by scanning the
submitted code, which for CH3 is one line: `from chemlab.cstr import run`).
"""

import math
from typing import Any, TypedDict


class InputSpec(TypedDict):
    unit: str
    default: float
    min: float
    max: float
    required: bool
    description: str


Values = dict[str, float]


def spec(
    unit: str, default: float, lo: float, hi: float, description: str
) -> InputSpec:
    return {
        "unit": unit,
        "default": default,
        "min": lo,
        "max": hi,
        "required": False,
        "description": description,
    }


def validate(
    raw: dict[str, Any], specs: dict[str, InputSpec]
) -> tuple[Values, list[dict[str, str]]]:
    """Fill defaults, accept plain numbers or {value, unit} in the canonical unit."""
    values: Values = {}
    errors: list[dict[str, str]] = []
    for name in raw:
        if name not in specs:
            errors.append(_err("unknown_input", f"unknown input '{name}'", name))
    for name, s in specs.items():
        item = raw.get(name, s["default"])
        if isinstance(item, dict):
            unit = item.get("unit", s["unit"])
            if unit != s["unit"]:
                errors.append(
                    _err(
                        "wrong_unit", f"{name} must be in {s['unit']}, got {unit}", name
                    )
                )
                continue
            item = item.get("value")
        if isinstance(item, bool) or not isinstance(item, int | float):
            errors.append(_err("not_a_number", f"{name} must be a number", name))
            continue
        x = float(item)
        if not math.isfinite(x) or not s["min"] <= x <= s["max"]:
            errors.append(
                _err(
                    "out_of_range",
                    f"{name} must be between {s['min']:g} and {s['max']:g} {s['unit']}",
                    name,
                )
            )
            continue
        values[name] = x
    return values, errors


def envelope(
    template: str, version: str, values: Values, specs: dict[str, InputSpec]
) -> dict[str, Any]:
    return {
        "template": template,
        "version": version,
        "ok": True,
        "errors": [],
        "warnings": [],
        "inputs": {
            n: {"value": v, "unit": specs[n]["unit"]} for n, v in values.items()
        },
        "outputs": {},
        "steady_states": [],
        "n_steady_states": 0,
        "series": {},
        "geometry": {},
    }


def failed(template: str, version: str, errors: list[dict[str, str]]) -> dict[str, Any]:
    out = envelope(template, version, {}, {})
    out.update(ok=False, errors=errors)
    return out


def series(x: Any, y: Any, x_unit: str, y_unit: str) -> dict[str, Any]:
    return {"x": list(x), "y": list(y), "x_unit": x_unit, "y_unit": y_unit}


def json_safe(obj: Any, warnings: list[str], path: str = "") -> Any:
    """Plain Python types only; NaN/inf become None with a warning (the sandbox
    serialises with allow_nan=False, so one NaN would fail the whole run)."""
    if isinstance(obj, dict):
        return {
            k: json_safe(v, warnings, f"{path}.{k}" if path else k)
            for k, v in obj.items()
        }
    if isinstance(obj, list | tuple):
        return [json_safe(v, warnings, path) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if hasattr(obj, "item"):  # numpy scalar
        obj = obj.item()
    if isinstance(obj, int):
        return obj
    x = float(obj)
    if not math.isfinite(x):
        msg = f"non-finite value replaced by null in {path}"
        if msg not in warnings:
            warnings.append(msg)
        return None
    return x


def _err(code: str, message: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "field": field}


def finish(out: dict[str, Any]) -> dict[str, Any]:
    """Make a template's result JSON-safe; warnings from cleaning are kept."""
    warnings = list(out["warnings"])
    clean = json_safe({k: v for k, v in out.items() if k != "warnings"}, warnings)
    clean["warnings"] = warnings
    return {k: clean[k] for k in out}
