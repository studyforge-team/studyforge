"""Isothermal flash template: ideal liquid and ideal gas (Raoult's law), 2 or 3 compounds.

Compounds come from the 40-compound table in _compounds.py (numbers c1, c2, c3; c3 = 0
means a binary). Feed amounts n1..n3 are normalised to mole fractions z.

    Psat_i(T) = 10^(A_i - B_i / (T + C_i))  Pa  (Poling Antoine constants)
    K_i = Psat_i / P
    bubble pressure  P_bubble = sum z_i Psat_i       dew pressure  P_dew = 1 / sum(z_i / Psat_i)

Bubble/dew check first: P >= P_bubble is all liquid (V/F = 0), P <= P_dew all vapour
(V/F = 1). Otherwise Rachford-Rice, sum z_i (K_i - 1) / (1 + V (K_i - 1)) = 0, solved for
V/F in (0, 1) with brentq; x_i = z_i / (1 + V (K_i - 1)), y_i = K_i x_i (denominators evaluated as
L + V K_i, and for V > 0.5 the unknown is the liquid fraction L, so tiny K or a
liquid of 1e-15 of the feed stays accurate).
Bubble and dew temperatures at P are solved the same way in T. For a binary, the series
give the T-x-y diagram at P.

Warnings: the flash T, a solved bubble/dew T or the T-x-y curve outside a present
compound's Antoine range (extrapolated) or above its critical temperature (Raoult's
law does not apply). Ideal only: no activity
coefficients, so azeotropes (e.g. ethanol-water) are not predicted.
"""

import math
from typing import Any

import numpy as np
from scipy.optimize import brentq

from ._common import InputSpec, _err, envelope, failed, finish, series, spec, validate
from ._compounds import COMPOUNDS

TEMPLATE = "flash"
VERSION = "1.0"
N_SERIES = 41
T_MAX = 2000.0  # K, upper bracket for bubble/dew temperature
LOG10_PSAT_FLOOR = -250.0  # lower bracket: every Psat >= 1e-250 Pa
NUMBERS = ", ".join(f"{i} {r['name']}" for i, r in enumerate(COMPOUNDS, 1))
N = len(COMPOUNDS)

SPEC: dict[str, InputSpec] = {
    "c1": spec("-", 14.0, 1.0, N, f"compound 1 number: {NUMBERS}"),
    "c2": spec("-", 15.0, 1.0, N, "compound 2 number (same list as c1)"),
    "c3": spec("-", 0.0, 0.0, N, "compound 3 number (0 = binary)"),
    "n1": spec("-", 0.5, 0.0, 1e6, "feed amount of compound 1 (normalised)"),
    "n2": spec("-", 0.5, 0.0, 1e6, "feed amount of compound 2 (normalised)"),
    "n3": spec("-", 0.0, 0.0, 1e6, "feed amount of compound 3 (normalised)"),
    "T": spec("K", 368.15, 50.0, 1000.0, "flash temperature"),
    "P": spec("Pa", 101325.0, 100.0, 1e8, "flash pressure"),
}


def run(inputs: dict[str, Any] | None = None, series: bool = True) -> dict[str, Any]:
    with np.errstate(all="ignore"):
        return _run(inputs or {}, series)


def psat(r: dict[str, Any], t: float) -> float:
    """Antoine vapour pressure; 0 below the equation's pole (T + C <= 0)."""
    return 10.0 ** (r["A"] - r["B"] / (t + r["C"])) if t + r["C"] > 0 else 0.0


def _t_floor(r: dict[str, Any]) -> float:
    """T at which this compound's Psat is 10^-250 Pa (keeps logs and ratios finite)."""
    return -r["C"] + r["B"] / (r["A"] - LOG10_PSAT_FLOOR)


def bubble_t(rs: list[dict[str, Any]], z: list[float], p: float) -> float | None:
    used = [(r, zi) for r, zi in zip(rs, z, strict=True) if zi > 0]

    def f(t: float) -> float:
        s = math.fsum(zi * psat(r, t) for r, zi in used)
        return math.log(s / p) if s > 0 else -math.inf

    # the most volatile present compound alone keeps the sum positive at the bracket
    return _root(f, min(_t_floor(r) for r, _ in used), T_MAX)


def dew_t(rs: list[dict[str, Any]], z: list[float], p: float) -> float | None:
    used = [(r, zi) for r, zi in zip(rs, z, strict=True) if zi > 0]

    def f(t: float) -> float:
        return -math.log(p * math.fsum(zi / psat(r, t) for r, zi in used))

    # every present compound needs Psat > 0 here
    return _root(f, max(_t_floor(r) for r, _ in used), T_MAX)


def _root(f: Any, lo: float, hi: float) -> float | None:
    flo, fhi = f(lo), f(hi)
    if not (math.isfinite(flo) and math.isfinite(fhi)) or flo > 0 or fhi < 0:
        return None
    return float(brentq(f, lo, hi, xtol=1e-12, rtol=1e-14, maxiter=500))


def _rr(z: list[float], k: list[float], liquid: float, vapour: float) -> float:
    """Rachford-Rice sum at liquid fraction L and vapour fraction V = 1 - L; the
    denominators 1 + V (K - 1) are written L + V K so that neither cancels."""
    return math.fsum(
        zi * (ki - 1) / (liquid + vapour * ki) for zi, ki in zip(z, k, strict=True)
    )


def rachford_rice(z: list[float], k: list[float]) -> tuple[float, float] | None:
    """(V, L) of the two-phase solution, or None when the feed is single phase.

    The phase test uses the same sum as the root, so a pressure within rounding of the
    bubble or dew pressure cannot reach brentq without a sign change. Near V = 1 the
    unknown is L, so a liquid of 1e-15 of the feed still gets accurate x."""
    if _rr(z, k, 1.0, 0.0) <= 0:  # sum z K <= 1: at or above the bubble pressure
        return None
    tiny = 1e-300  # > 0 so a K = 0 compound never makes L + V K zero
    if _rr(z, k, tiny, 1.0 - tiny) >= 0:  # sum z / K <= 1: at or below the dew pressure
        return None
    if _rr(z, k, 0.5, 0.5) >= 0:  # root in V >= 0.5: solve for L in (0, 0.5]
        liq = brentq(
            lambda x: _rr(z, k, x, 1 - x),
            tiny,
            0.5,
            xtol=1e-300,
            rtol=1e-15,
            maxiter=2000,
        )
        return 1 - liq, liq
    vap = brentq(
        lambda x: _rr(z, k, 1 - x, x), 0.0, 0.5, xtol=1e-300, rtol=1e-15, maxiter=2000
    )
    return vap, 1 - vap


def _run(inputs: dict[str, Any], want_series: bool) -> dict[str, Any]:
    p, errors = validate(inputs, SPEC)
    if not errors:
        errors = _check(p)
    if errors:
        return failed(TEMPLATE, VERSION, errors)
    out = envelope(TEMPLATE, VERSION, p, SPEC)
    warn = out["warnings"]
    nums = [int(p["c1"]), int(p["c2"])] + ([int(p["c3"])] if p["c3"] else [])
    rs = [COMPOUNDS[i - 1] for i in nums]
    amounts = [p["n1"], p["n2"], p["n3"]][: len(rs)]
    if not p["c3"] and p["n3"] > 0:
        warn.append("n3 ignored: no compound 3 (c3 = 0)")
    z = [a / sum(amounts) for a in amounts]
    t, pr = p["T"], p["P"]
    cold = [
        r["name"] for r, zi in zip(rs, z, strict=True) if zi > 0 and t + r["C"] <= 0
    ]
    if cold:
        msg = f"T is below where the Antoine equation is defined for {', '.join(cold)}"
        return failed(TEMPLATE, VERSION, [_err("temperature_too_low", msg, "T")])
    present = [r for r, zi in zip(rs, z, strict=True) if zi > 0]
    warn.extend(_range_warnings(present, "T", [t]))
    ps = [psat(r, t) for r in rs]
    k = [x / pr for x in ps]
    p_bub = math.fsum(zi * x for zi, x in zip(z, ps, strict=True))
    # a heavy compound's Psat can underflow to 0 far below its range: no dew point then
    inv = math.fsum(
        zi / x if x > 0 else math.inf for zi, x in zip(z, ps, strict=True) if zi > 0
    )
    p_dew = 0.0 if math.isinf(inv) else 1 / inv
    two_phase = rachford_rice(z, k)
    if two_phase is not None:
        v, liq = two_phase
        xs = [zi / (liq + v * ki) for zi, ki in zip(z, k, strict=True)]
        ys = [ki * xi for ki, xi in zip(k, xs, strict=True)]
    elif _rr(z, k, 1.0, 0.0) <= 0:
        v, xs, ys = 0.0, z, None
        warn.append(
            "all liquid at these conditions (P at or above the bubble pressure)"
        )
    else:
        v, xs, ys = 1.0, None, z
        warn.append("all vapour at these conditions (P at or below the dew pressure)")
    o: dict[str, tuple[float, str]] = {
        "P_bubble": (p_bub, "Pa"),
        "P_dew": (p_dew, "Pa"),
        "V_frac": (v, "-"),
    }
    for name, value in (("T_bubble", bubble_t(rs, z, pr)), ("T_dew", dew_t(rs, z, pr))):
        if value is None:
            warn.append(f"{name} at P not found below {T_MAX:g} K")
        else:
            o[name] = (value, "K")
            warn.extend(_range_warnings(present, name, [value]))
    for i in range(len(rs)):
        o[f"z{i + 1}"] = (z[i], "-")
        o[f"Psat{i + 1}"] = (ps[i], "Pa")
        o[f"K{i + 1}"] = (k[i], "-")
        if xs is not None:
            o[f"x{i + 1}"] = (xs[i], "-")
        if ys is not None:
            o[f"y{i + 1}"] = (ys[i], "-")
    out["outputs"] = {key: {"value": val, "unit": u} for key, (val, u) in o.items()}
    out["geometry"] = {"type": "flash_drum", "components": [r["name"] for r in rs]}
    if want_series and len(rs) == 2:
        out["series"] = _txy(rs, pr)
        ts = out["series"]["T_x"]["y"]
        if len(ts) < N_SERIES:
            warn.append(f"T-x-y: {N_SERIES - len(ts)} of {N_SERIES} points not found")
        warn.extend(_range_warnings(rs, "T-x-y", ts))
    return finish(out)


def _check(p: dict[str, float]) -> list[dict[str, str]]:
    for name in ("c1", "c2", "c3"):
        if p[name] != round(p[name]):
            return [
                _err("not_an_integer", f"{name} must be a whole compound number", name)
            ]
    if p["c2"] == p["c1"]:
        return [_err("same_compound", "choose different compounds", "c2")]
    if p["c3"] in (p["c1"], p["c2"]):
        return [_err("same_compound", "choose different compounds", "c3")]
    nums = [p["c1"], p["c2"]] + ([p["c3"]] if p["c3"] else [])
    if sum([p["n1"], p["n2"], p["n3"]][: len(nums)]) <= 0:
        return [_err("empty_feed", "the feed amounts must not all be zero", "n1")]
    return []


def _range_warnings(rs: list[dict[str, Any]], what: str, ts: list[float]) -> list[str]:
    """Warn when a temperature leaves a compound's Antoine range or passes its Tc."""
    out = []
    for r in rs:
        if ts and not all(r["Tmin"] <= t <= r["Tmax"] for t in ts):
            out.append(
                f"{r['name']}: {what} outside its Antoine range"
                f" {r['Tmin']:g}-{r['Tmax']:g} K (extrapolated)"
            )
        if ts and max(ts) > r["Tc"]:
            out.append(
                f"{r['name']}: {what} above its critical temperature;"
                " Raoult's law does not apply"
            )
    return out


def _txy(rs: list[dict[str, Any]], pr: float) -> dict[str, Any]:
    """T-x-y diagram at P: bubble temperature for liquid x1, and the vapour y1 there."""
    xs, ts, ys = [], [], []
    for x1 in np.linspace(0.0, 1.0, N_SERIES):
        t = bubble_t(rs, [float(x1), 1 - float(x1)], pr)
        if t is None:
            continue
        xs.append(float(x1))
        ts.append(t)
        ys.append(float(x1) * psat(rs[0], t) / pr)
    return {"T_x": series(xs, ts, "-", "K"), "T_y": series(ys, ts, "-", "K")}
