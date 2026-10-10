"""McCabe-Thiele template: binary distillation, constant relative volatility alpha,
constant molar overflow, total condenser, partial reboiler counted as a stage.

Conventions chosen here (flows in kmol/h, compositions are mole fractions of the
light key):
- Balances: D = F (zF - xB)/(xD - xB), B = F - D.
- Equilibrium y = alpha x/(1 + (alpha-1) x); inverse x = y/(alpha - (alpha-1) y).
- q-line through (zF, zF), slope q/(q-1); |q-1| < 1e-9 is vertical (x = zF) and
  |q| < 1e-9 is horizontal (y = zF).
- Rmin = (xD - y*)/(y* - x*) from the q-line / equilibrium intersection (x*, y*),
  found with brentq (closed form for the vertical and horizontal cases). If R > 0
  it is used as given (must exceed Rmin), else R = R_factor * Rmin.
- Stripping line passes through (xB, xB) and the rectifying/q-line intersection.
- Stages are stepped from the top, starting at (xD, xD): horizontal to the
  equilibrium curve, then vertical to the operating line. A stage whose liquid x is
  above the operating-line intersection x_i uses the rectifying line; the first stage
  with x <= x_i is the feed stage and it, and all later stages, use the stripping
  line. Stepping stops at the first stage with x <= xB. N_theoretical counts whole
  stages (the last, partial step counts as a full stage, the reboiler is the last
  stage). N_fractional = (N-1) + (x_prev - xB)/(x_prev - x_last).
- More than 200 stages (near-pinch) returns ok=False with code "too_many_stages".
- Theoretical trays = N - 1; real trays = ceil((N - 1)/Eo); feed tray =
  max(1, round(feed_stage/Eo)); tray spacing 0.6 m.
- The "stages" series is the staircase polyline from (xD, xD) to the last
  equilibrium point (x_N, y_{N-1}) (the final vertical step is not drawn). It is
  evenly thinned to 200 points if a column needs more than 99 stages.
- Illustrative Souders-Brown diameter (not a design): K = 0.07 m/s (0.6 m tray
  spacing), rho_V = P*MW_top/(1000*R*T_top) with R = 8.314462618 J/(mol K),
  u_max = K*sqrt((rho_L - rho_V)/rho_V), vapour V = (R+1) D and V' = V - (1-q) F
  (kmol/h), sized on the larger; mass flow = Vmax*MW_top/3600 kg/s, volumetric
  flow = mass/rho_V, area = volumetric/u_max, diameter = sqrt(4 area/pi). There is
  no flooding fraction.
"""

import math
from typing import Any

import numpy as np
from scipy.optimize import brentq

from ._common import InputSpec, Values, envelope, failed, finish, series, spec, validate

TEMPLATE = "mccabe"
VERSION = "1.0"
R_GAS = 8.314462618  # J/(mol K)
K_SB = 0.07  # m/s, Souders-Brown constant at 0.6 m tray spacing
TRAY_SPACING = 0.6  # m
MAX_STAGES = 200
MAX_POINTS = 200
N_EQ = 101

SPEC: dict[str, InputSpec] = {
    "F": spec("kmol/h", 100.0, 1e-6, 1e9, "feed flow"),
    "zF": spec("-", 0.5, 1e-6, 1 - 1e-6, "feed light-key mole fraction"),
    "xD": spec("-", 0.95, 1e-6, 1 - 1e-6, "distillate light-key mole fraction"),
    "xB": spec("-", 0.05, 1e-6, 1 - 1e-6, "bottoms light-key mole fraction"),
    "q": spec("-", 1.0, -2.0, 3.0, "feed thermal condition (1 = sat. liquid)"),
    "alpha": spec("-", 2.5, 1.0, 100.0, "relative volatility (must be > 1)"),
    "R": spec("-", 0.0, 0.0, 1e6, "reflux ratio L/D (0 = not given, use R_factor)"),
    "R_factor": spec("-", 1.3, 1.0001, 1e4, "R / Rmin, used when R = 0"),
    "Eo": spec("-", 0.7, 0.05, 1.0, "overall tray efficiency"),
    "P": spec("Pa", 101325.0, 1e3, 1e8, "column top pressure"),
    "T_top": spec("K", 353.0, 100.0, 1000.0, "top vapour temperature"),
    "MW_top": spec("kg/kmol", 78.11, 1.0, 1000.0, "top vapour molar mass"),
    "rho_L": spec("kg/m^3", 800.0, 100.0, 5000.0, "liquid density"),
}


def run(inputs: dict[str, Any] | None = None, series: bool = True) -> dict[str, Any]:
    with np.errstate(all="ignore"):
        return _run(inputs or {}, series)


def _eq(alpha: float, x: Any) -> Any:
    return alpha * x / (1.0 + (alpha - 1.0) * x)


def _inv(alpha: float, y: Any) -> Any:
    return y / (alpha - (alpha - 1.0) * y)


def _err(code: str, message: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "field": field}


def _check(p: Values) -> list[dict[str, str]]:
    errors = []
    if not p["xB"] < p["zF"]:
        errors.append(_err("bad_compositions", "need 0 < xB < zF < xD < 1", "xB"))
    elif not p["zF"] < p["xD"]:
        errors.append(_err("bad_compositions", "need 0 < xB < zF < xD < 1", "xD"))
    if not p["alpha"] > 1.0:
        errors.append(_err("bad_alpha", "alpha must be greater than 1", "alpha"))
    return errors


def _q_intersection(p: Values) -> tuple[float, float]:
    """(x*, y*): q-line meets the equilibrium curve."""
    a, zF, q = p["alpha"], p["zF"], p["q"]
    if abs(q - 1.0) < 1e-9:
        return zF, float(_eq(a, zF))
    if abs(q) < 1e-9:
        return float(_inv(a, zF)), zF
    m, c = q / (q - 1.0), -zF / (q - 1.0)

    def g(x: float) -> float:
        return float(_eq(a, x)) - (m * x + c)

    # g(zF) > 0; the root is above zF for q > 1 and below it for q < 1
    lo, hi = (zF, 1.0) if q > 1.0 else (0.0, zF)
    x = float(brentq(g, lo, hi, xtol=1e-15, rtol=1e-14))
    return x, m * x + c


def _lines(p: Values, R: float) -> tuple[float, float, float] | None:
    """(x_i, y_i, stripping slope): rectifying/q-line intersection, or None if the
    operating lines are degenerate."""
    zF, q = p["zF"], p["q"]
    s, b = R / (R + 1.0), p["xD"] / (R + 1.0)
    if abs(q - 1.0) < 1e-9:
        xi = zF
    elif abs(q) < 1e-9:
        xi = (zF - b) / s
    else:
        m, c = q / (q - 1.0), -zF / (q - 1.0)
        if abs(s - m) < 1e-12:
            return None
        xi = (c - b) / (s - m)
    yi = s * xi + b
    if not math.isfinite(xi) or not p["xB"] < xi < p["xD"]:
        return None
    return xi, yi, (yi - p["xB"]) / (xi - p["xB"])


def _run(inputs: dict[str, Any], want_series: bool) -> dict[str, Any]:
    values, errors = validate(inputs, SPEC)
    if not errors:
        errors = _check(values)
    if errors:
        return failed(TEMPLATE, VERSION, errors)
    p = values
    out = envelope(TEMPLATE, VERSION, values, SPEC)
    a, F, q = p["alpha"], p["F"], p["q"]
    xs, ys = _q_intersection(p)
    rmin = (p["xD"] - ys) / (ys - xs)
    if not rmin > 0.0:
        msg = "no finite minimum reflux (xD too low)"
        return failed(TEMPLATE, VERSION, [_err("infeasible_separation", msg, "xD")])
    if p["R"] > 0.0 and p["R"] <= rmin:
        msg = f"R must exceed Rmin = {rmin:.6g}"
        return failed(TEMPLATE, VERSION, [_err("reflux_below_minimum", msg, "R")])
    R = p["R"] if p["R"] > 0.0 else p["R_factor"] * rmin
    vapour_rho = p["P"] * p["MW_top"] / (1000.0 * R_GAS * p["T_top"])
    if vapour_rho >= p["rho_L"]:
        msg = "vapour density must be below rho_L"
        return failed(TEMPLATE, VERSION, [_err("bad_vapour_density", msg, "rho_L")])
    geo = _lines(p, R)
    if geo is None:
        msg = "operating lines do not intersect"
        return failed(TEMPLATE, VERSION, [_err("degenerate_operating_lines", msg, "R")])
    xi, yi, slope = geo
    s, b = R / (R + 1.0), p["xD"] / (R + 1.0)

    px, py = [p["xD"]], [p["xD"]]  # staircase polyline
    y, x_prev, x = p["xD"], p["xD"], p["xD"]
    feed = 0
    n = 0
    for i in range(1, MAX_STAGES + 1):
        x = float(_inv(a, y))
        if not feed and x <= xi:
            feed = i
        px.append(x)
        py.append(y)
        if x <= p["xB"]:
            n = i
            break
        y = p["xB"] + slope * (x - p["xB"]) if feed else s * x + b
        px.append(x)
        py.append(y)
        x_prev = x
    if n == 0:
        out["ok"] = False
        out["errors"].append(
            _err("too_many_stages", f"more than {MAX_STAGES} stages (near-pinch)", "R")
        )
        return finish(out)
    n_frac = (n - 1) + (x_prev - p["xB"]) / (x_prev - x)
    theo = n - 1
    real = math.ceil(theo / p["Eo"])
    D = F * (p["zF"] - p["xB"]) / (p["xD"] - p["xB"])
    V = (R + 1.0) * D
    V_bar = V - (1.0 - q) * F
    u_max = K_SB * math.sqrt((p["rho_L"] - vapour_rho) / vapour_rho)
    mass = max(V, V_bar) * p["MW_top"] / 3600.0
    area = mass / vapour_rho / u_max
    diameter = math.sqrt(4.0 * area / math.pi)
    o = {
        "D": (D, "kmol/h"),
        "B": (F - D, "kmol/h"),
        "Rmin": (rmin, "-"),
        "R": (R, "-"),
        "N_theoretical": (n, "-"),
        "N_fractional": (n_frac, "-"),
        "theoretical_trays": (theo, "-"),
        "real_trays": (real, "-"),
        "feed_stage": (feed, "-"),
        "V": (V, "kmol/h"),
        "V_bar": (V_bar, "kmol/h"),
        "rho_V": (vapour_rho, "kg/m^3"),
        "u_max": (u_max, "m/s"),
        "diameter_m": (diameter, "m"),
        "x_star": (xs, "-"),
        "y_star": (ys, "-"),
    }
    out["outputs"] = {k: {"value": v, "unit": u} for k, (v, u) in o.items()}
    out["geometry"] = {
        "type": "column",
        "diameter_m": diameter,
        "height_m": real * TRAY_SPACING,
        "n_trays": real,
        "feed_tray": max(1, round(feed / p["Eo"])),
    }
    if want_series:
        xe = np.linspace(0.0, 1.0, N_EQ)
        if len(px) > MAX_POINTS:
            pick = np.linspace(0, len(px) - 1, MAX_POINTS)
            idx = np.unique(np.round(pick).astype(int))
            px, py = [px[i] for i in idx], [py[i] for i in idx]
        out["series"] = {
            "equilibrium": series(xe, _eq(a, xe), "-", "-"),
            "diagonal": series([0.0, 1.0], [0.0, 1.0], "-", "-"),
            "rectifying_line": series([xi, p["xD"]], [yi, p["xD"]], "-", "-"),
            "stripping_line": series([p["xB"], xi], [p["xB"], yi], "-", "-"),
            "q_line": series([p["zF"], xs], [p["zF"], ys], "-", "-"),
            "stages": series(px, py, "-", "-"),
        }
    return finish(out)
