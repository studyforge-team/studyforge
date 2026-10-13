"""Pipe and pump template: incompressible liquid, tank 1 -> tank 2, one straight pipe.

Energy balance per unit weight (tank surfaces at rest, so no kinetic-energy term):

    head = h_major + h_minor + h_static                    (m of liquid)
    u = 4 Q / (pi D^2),   Re = rho u D / mu
    h_major = f (L/D) u^2 / (2 g)      Darcy-Weisbach
    h_minor = K u^2 / (2 g)            K = sum of minor-loss coefficients
    h_static = dz + dP / (rho g)       dz = z2 - z1, dP = p2 - p1

Darcy friction factor f:
    Re < 2300:        f = 64/Re (laminar, independent of roughness)
    Re >= 2300:       Colebrook-White, 1/sqrt(f) = -2 log10(eps/(3.7 D) + 2.51/(Re sqrt(f))),
                      solved for x = 1/sqrt(f) with scipy brentq.
    2300 <= Re < 4000 uses Colebrook too, with a warning (value is uncertain).
Power: P_hydraulic = rho g Q head, P_shaft = P_hydraulic / eta, dP_friction = rho g h_major.
If head < 0 gravity/pressure alone drives the flow: head is reported (negative), both
powers are set to 0 and a "no pump needed" warning is added (no turbine recovery).
Assumptions: constant properties, fully developed flow, no entrance/exit effects other
than those in K, g = 9.80665 m/s^2, eps < D/2. The system curve (series head_curve) is
the head needed at flow q in [0, 2 Q], friction recomputed per point; at q = 0 it is h_static.
"""

import math
from typing import Any

import numpy as np
from scipy.optimize import brentq

from ._common import InputSpec, Values, _err, envelope, failed, finish, spec, validate
from ._common import series as make_series

TEMPLATE = "pipe"
VERSION = "1.0"
G = 9.80665  # m/s^2
RE_LAMINAR = 2300.0
RE_TURBULENT = 4000.0
N_SERIES = 60

SPEC: dict[str, InputSpec] = {
    "Q": spec("m^3/s", 0.01, 1e-7, 10.0, "volumetric flow"),
    "D": spec("m", 0.1, 0.005, 2.0, "pipe inner diameter"),
    "L": spec("m", 100.0, 0.1, 1e5, "pipe length"),
    "eps": spec("m", 4.5e-5, 0.0, 0.01, "absolute roughness (commercial steel 4.5e-5)"),
    "rho": spec("kg/m^3", 997.0, 500.0, 2000.0, "liquid density"),
    "mu": spec("Pa s", 8.9e-4, 1e-4, 1.0, "dynamic viscosity"),
    "K_fittings": spec("-", 5.0, 0.0, 1000.0, "sum of minor-loss coefficients"),
    "dz": spec("m", 10.0, -1000.0, 1000.0, "elevation rise z2 - z1"),
    "dP": spec("Pa", 0.0, -1e7, 1e7, "extra pressure rise p2 - p1"),
    "eta": spec("-", 0.7, 0.05, 1.0, "pump efficiency"),
}


def run(inputs: dict[str, Any] | None = None, series: bool = True) -> dict[str, Any]:
    with np.errstate(all="ignore"):
        return _run(inputs or {}, series)


def friction_factor(re: float, e_d: float) -> float:
    """Darcy friction factor: 64/Re below 2300, Colebrook-White otherwise."""
    if re < RE_LAMINAR:
        return 64.0 / re

    # x = 1/sqrt(f); g(x) < 0 at x = 1e-3 and > 0 at x = 1e3 for any eps/D < 0.5
    def g(x: float) -> float:
        return x + 2.0 * math.log10(e_d / 3.7 + 2.51 * x / re)

    x = brentq(g, 1e-3, 1e3, xtol=1e-14, rtol=4 * np.finfo(float).eps, maxiter=200)
    return 1.0 / (x * x)


def _heads(p: Values, q: float) -> tuple[float, float, float, float, float]:
    """(u, Re, f, h_major, h_minor) at flow q (> 0)."""
    u = 4.0 * q / (math.pi * p["D"] ** 2)
    re = p["rho"] * u * p["D"] / p["mu"]
    f = friction_factor(re, p["eps"] / p["D"])
    h_major = f * p["L"] / p["D"] * u * u / (2.0 * G)
    h_minor = p["K_fittings"] * u * u / (2.0 * G)
    return u, re, f, h_major, h_minor


def _run(inputs: dict[str, Any], series: bool) -> dict[str, Any]:
    values, errors = validate(inputs, SPEC)
    if not errors and values["eps"] >= values["D"] / 2.0:
        errors.append(_err("roughness_too_large", "eps must be less than D/2", "eps"))
    if errors:
        return failed(TEMPLATE, VERSION, errors)
    out = envelope(TEMPLATE, VERSION, values, SPEC)
    p = values
    u, re, f, h_major, h_minor = _heads(p, p["Q"])
    h_static = _static(p)
    head = h_major + h_minor + h_static
    if RE_LAMINAR <= re < RE_TURBULENT:
        out["warnings"].append(
            f"transitional flow (Re = {re:.0f}): friction factor is uncertain"
        )
    p_hyd = p["rho"] * G * p["Q"] * head
    if head < 0.0:
        p_hyd = 0.0
        out["warnings"].append(
            f"no pump needed: required head {head:.3g} m is negative (flow runs by gravity/pressure)"
        )
    out["outputs"] = {
        "u": {"value": u, "unit": "m/s"},
        "Re": {"value": re, "unit": "-"},
        "f_darcy": {"value": f, "unit": "-"},
        "h_major": {"value": h_major, "unit": "m"},
        "h_minor": {"value": h_minor, "unit": "m"},
        "h_static": {"value": h_static, "unit": "m"},
        "head": {"value": head, "unit": "m"},
        "P_hydraulic": {"value": p_hyd, "unit": "W"},
        "P_shaft": {"value": p_hyd / p["eta"], "unit": "W"},
        "dP_friction": {"value": p["rho"] * G * h_major, "unit": "Pa"},
    }
    out["geometry"] = {
        "type": "pipe",
        "diameter_m": p["D"],
        "length_m": p["L"],
        "dz_m": p["dz"],
    }
    if series:
        qs = np.linspace(0.0, 2.0 * p["Q"], N_SERIES)
        heads = [
            h_static if q == 0.0 else sum(_heads(p, float(q))[3:]) + h_static
            for q in qs
        ]
        out["series"] = {"head_curve": series_(qs, heads)}
    return finish(out)


def _static(p: Values) -> float:
    return p["dz"] + p["dP"] / (p["rho"] * G)


def series_(x: Any, y: Any) -> dict[str, Any]:
    return make_series(x, y, "m^3/s", "m")
