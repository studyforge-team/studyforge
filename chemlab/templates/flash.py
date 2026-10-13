"""Isothermal flash template: ideal liquid and ideal gas (Raoult's law), 2 or 3 compounds.

Compounds come from the 40-compound table in _compounds.py (numbers c1, c2, c3; c3 = 0
means a binary). Feed amounts n1..n3 are normalised to mole fractions z.

    Psat_i(T) = 10^(A_i - B_i / (T + C_i))  Pa  (Poling Antoine constants)
    K_i = Psat_i / P
    bubble pressure  P_bubble = sum z_i Psat_i       dew pressure  P_dew = 1 / sum(z_i / Psat_i)

Bubble/dew check first: P >= P_bubble is all liquid (V/F = 0), P <= P_dew all vapour
(V/F = 1). Otherwise Rachford-Rice, sum z_i (K_i - 1) / (1 + V (K_i - 1)) = 0, solved for
V/F in (0, 1) with brentq; x_i = z_i / (1 + V (K_i - 1)), y_i = K_i x_i (denominators evaluated as
(1 - V) + V K_i so a tiny K does not round them to 0).
Bubble and dew temperatures at P are solved the same way in T. For a binary, the series
give the T-x-y diagram at P.

Warnings: T outside a compound's Antoine range (extrapolated), T above a compound's
critical temperature (Raoult's law does not apply). Ideal only: no activity
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
    return 10.0 ** (r["A"] - r["B"] / (t + r["C"]))


def _t_low(rs: list[dict[str, Any]]) -> float:
    """Lowest T at which every Psat is at least 10^-250 Pa (finite logs and ratios)."""
    return max(-r["C"] + r["B"] / (r["A"] - LOG10_PSAT_FLOOR) for r in rs)


def bubble_t(rs: list[dict[str, Any]], z: list[float], p: float) -> float | None:
    def f(t: float) -> float:
        return math.log(sum(zi * psat(r, t) for r, zi in zip(rs, z, strict=True)) / p)

    return _root(f, _t_low(rs), T_MAX)


def dew_t(rs: list[dict[str, Any]], z: list[float], p: float) -> float | None:
    def f(t: float) -> float:
        return -math.log(p * sum(zi / psat(r, t) for r, zi in zip(rs, z, strict=True)))

    return _root(f, _t_low(rs), T_MAX)


def _root(f: Any, lo: float, hi: float) -> float | None:
    flo, fhi = f(lo), f(hi)
    if not (math.isfinite(flo) and math.isfinite(fhi)) or flo > 0 or fhi < 0:
        return None
    return float(brentq(f, lo, hi, xtol=1e-12, rtol=1e-14, maxiter=500))


def _den(v: float, k: float) -> float:
    """1 + V (K - 1), written so tiny K does not cancel to 0 at V = 1."""
    return (1 - v) + v * k


def rachford_rice(z: list[float], k: list[float]) -> float:
    def g(v: float) -> float:
        return sum(zi * (ki - 1) / _den(v, ki) for zi, ki in zip(z, k, strict=True))

    # K = 0 (Psat underflow) puts the pole 1/(1 - K) exactly at V = 1: stop one ulp short
    hi = 1.0 if min(k) > 0 else math.nextafter(1.0, 0.0)
    return float(brentq(g, 0.0, hi, xtol=1e-15, rtol=1e-15, maxiter=500))


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
    cold = [r["name"] for r in rs if t + r["C"] <= 0]
    if cold:
        msg = f"T is below where the Antoine equation is defined for {', '.join(cold)}"
        return failed(TEMPLATE, VERSION, [_err("temperature_too_low", msg, "T")])
    for r in rs:
        if not r["Tmin"] <= t <= r["Tmax"]:
            warn.append(
                f"{r['name']}: T outside its Antoine range {r['Tmin']:g}-{r['Tmax']:g} K"
                " (extrapolated)"
            )
        if t > r["Tc"]:
            warn.append(
                f"{r['name']}: T above its critical temperature; Raoult's law does not apply"
            )
    ps = [psat(r, t) for r in rs]
    k = [x / pr for x in ps]
    p_bub = sum(zi * x for zi, x in zip(z, ps, strict=True))
    # a heavy compound's Psat can underflow to 0 far below its range: no dew point then
    inv = math.fsum(
        zi / x if x > 0 else math.inf for zi, x in zip(z, ps, strict=True) if zi > 0
    )
    p_dew = 0.0 if math.isinf(inv) else 1 / inv
    if pr >= p_bub:
        v, xs, ys = 0.0, z, None
        warn.append(
            "all liquid at these conditions (P at or above the bubble pressure)"
        )
    elif pr <= p_dew:
        v, xs, ys = 1.0, None, z
        warn.append("all vapour at these conditions (P at or below the dew pressure)")
    else:
        v = rachford_rice(z, k)
        xs = [zi / _den(v, ki) for zi, ki in zip(z, k, strict=True)]
        ys = [ki * xi for ki, xi in zip(k, xs, strict=True)]
    o: dict[str, tuple[float, str]] = {
        "P_bubble": (p_bub, "Pa"),
        "P_dew": (p_dew, "Pa"),
        "V_frac": (v, "-"),
    }
    for name, value in (("T_bubble", bubble_t(rs, z, pr)), ("T_dew", dew_t(rs, z, pr))):
        if value is None:
            warn.append(
                f"{name} at P not found between {_t_low(rs):.1f} and {T_MAX:g} K"
            )
        else:
            o[name] = (value, "K")
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
    return finish(out)


def _check(p: dict[str, float]) -> list[dict[str, str]]:
    for name in ("c1", "c2", "c3"):
        if p[name] != round(p[name]):
            return [
                _err("not_an_integer", f"{name} must be a whole compound number", name)
            ]
    nums = [p["c1"], p["c2"]] + ([p["c3"]] if p["c3"] else [])
    if len(set(nums)) != len(nums):
        return [_err("same_compound", "choose different compounds", "c2")]
    if sum([p["n1"], p["n2"], p["n3"]][: len(nums)]) <= 0:
        return [_err("empty_feed", "the feed amounts must not all be zero", "n1")]
    return []


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
