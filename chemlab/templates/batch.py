"""Batch reactor template: isothermal, constant-density liquid, A -> products,
rate = k*CA^n.

Mole balance:  dCA/dt = -k*CA^n, solved in closed form (same kinetics and helpers as
pfr.py, with reaction time t in place of residence time). With Da = k*t*CA0^(n-1)
and m = n - 1:

    CA/CA0 = exp(-Da)  (n = 1),   CA/CA0 = (1 + m*Da)^(-1/m)  (n != 1)

For n < 1 the concentration reaches zero at a finite time and stays 0 (clamped).
Time for a target conversion (inverse, always finite for 0 < X_target < 1, k > 0):

    Da = -ln(1 - X)  (n = 1),   Da = ((1 - X)^(-m) - 1)/m  (n != 1),   t = Da/(k*CA0^m)
"""

import math
from typing import Any

import numpy as np

from ._common import InputSpec, Values, envelope, failed, finish, series, spec, validate
from .pfr import K_UNIT, KINETICS_SPEC, N_SERIES, conversion, rate_constant, remaining

TEMPLATE = "batch"
VERSION = "1.0"

SPEC: dict[str, InputSpec] = {
    "CA0": spec("mol/m^3", 1000.0, 1e-6, 1e5, "initial concentration of A"),
    "V": spec("m^3", 0.5, 1e-9, 1e5, "liquid volume"),
    **KINETICS_SPEC,
    "t": spec("s", 200.0, 0.0, 1e9, "reaction time"),
    "X_target": spec("-", 0.0, 0.0, 0.999999, "target conversion (0 = not used)"),
}


def run(inputs: dict[str, Any] | None = None, series: bool = True) -> dict[str, Any]:
    # overflow in extreme corners becomes inf -> null + warning, not stderr noise
    with np.errstate(all="ignore"):
        return _run(inputs or {}, series)


def _run(inputs: dict[str, Any], series: bool) -> dict[str, Any]:
    values, errors = validate(inputs, SPEC)
    if errors:
        return failed(TEMPLATE, VERSION, errors)
    out = envelope(TEMPLATE, VERSION, values, SPEC)
    p = values
    k = rate_constant(p)
    scale = k * p["CA0"] ** (p["n"] - 1.0)  # Da = scale * t
    if k <= 0.0:
        out["warnings"].append("k is zero (no reaction)")
    X = float(conversion(p["n"], scale * p["t"]))
    out["outputs"] = {
        "X": {"value": X, "unit": "-"},
        "X_percent": {"value": 100.0 * X, "unit": "%"},
        "CA": {
            "value": p["CA0"] * float(remaining(p["n"], scale * p["t"])),
            "unit": "mol/m^3",
        },
        "moles_reacted": {"value": p["CA0"] * X * p["V"], "unit": "mol"},
        "k_used": {"value": k, "unit": K_UNIT},
        "T": {"value": p["T"], "unit": "K"},
        "T_C": {"value": p["T"] - 273.15, "unit": "degC"},
    }
    t_target = 0.0
    if p["X_target"] > 0.0 and k > 0.0:
        t_target = time_for_conversion(p["n"], p["X_target"]) / scale
        out["outputs"]["t_for_target"] = {"value": t_target, "unit": "s"}
    d = (4.0 * p["V"] / math.pi) ** (1.0 / 3.0)  # H = D
    out["geometry"] = {
        "type": "batch",
        "volume_m3": p["V"],
        "diameter_m": d,
        "height_m": d,
    }
    if series:
        out["series"] = _series(p, scale, max(p["t"], t_target))
    return finish(out)


def time_for_conversion(n: float, x: float) -> float:
    """Dimensionless time Da = k*t*CA0^(n-1) that reaches conversion x (0 < x < 1)."""
    m = n - 1.0
    if m == 0.0:
        return -math.log1p(-x)
    return math.expm1(-m * math.log1p(-x)) / m


def _series(p: Values, scale: float, t_end: float) -> dict[str, Any]:
    t = np.linspace(0.0, t_end, N_SERIES)
    da = scale * t
    return {
        "concentration_time": series(
            t, p["CA0"] * remaining(p["n"], da), "s", "mol/m^3"
        ),
        "conversion_time": series(t, conversion(p["n"], da), "s", "-"),
    }
