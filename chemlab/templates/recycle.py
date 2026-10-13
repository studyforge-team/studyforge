"""Recycle flowsheet template: steady state, A -> B, inert I in the fresh feed.

Flowsheet: fresh feed F0 + recycle R -> mixer -> reactor (single-pass conversion Xsp
of A) -> separator -> splitter (purge fraction p, rest recycled to the mixer).
Fresh feed: F0A = F0*(1 - yI0), F0I = F0*yI0 (kmol/h). Reactor inlet = fresh + R.
Reactor outlet: A: (1 - Xsp)*rinA, B: Xsp*rinA, I: rinI (no side reactions).
Separator: all B leaves with the product; fraction sA of the unreacted A and sI of
the inert go overhead, the rest leave with the product. Splitter: purge = p*overhead,
recycle = (1 - p)*overhead.

Tear-stream equations (unknowns R_A, R_I), solved with scipy.optimize.fsolve from
zero recycle (flows scaled by F0):
    R_A = a*(F0A + R_A),  a = (1 - Xsp)*sA*(1 - p)
    R_I = b*(F0I + R_I),  b = sI*(1 - p)
The balances are linear, so the closed form is a check (warning if > 1e-6 relative):
    R_A = a*F0A/(1 - a),   R_I = b*F0I/(1 - b)
Degenerate cases: 1 - a = 0 needs Xsp = 0, which the input range excludes (A always
reacts), so A never accumulates. 1 - b = 0 needs sI = 1 and p = 0: inert then has no
exit, and with yI0 > 0 the recycle grows without bound -> error "inert_accumulates"
(field "p"). With yI0 = 0 there is no inert, so R_I = 0 and the case is fine.
Assumptions: isothermal, constant flows in kmol/h, no volume or pressure effects,
perfect separator splits, no reactor kinetics (conversion is given).
"""

from typing import Any

import numpy as np
from scipy.optimize import fsolve

from ._common import (
    InputSpec,
    Values,
    _err,
    envelope,
    failed,
    finish,
    series,
    spec,
    validate,
)

TEMPLATE = "recycle"
VERSION = "1.0"
N_SERIES = 60
RATIO_WARN = 1000.0
CLOSURE_TOL = 1e-6

SPEC: dict[str, InputSpec] = {
    "F0": spec("kmol/h", 100.0, 1e-3, 1e6, "fresh feed molar flow"),
    "yI0": spec("-", 0.01, 0.0, 0.5, "inert mole fraction in the fresh feed"),
    "Xsp": spec("-", 0.3, 1e-4, 1.0, "single-pass conversion of A in the reactor"),
    "sA": spec("-", 0.95, 0.0, 1.0, "fraction of unreacted A going overhead"),
    "sI": spec("-", 1.0, 0.0, 1.0, "fraction of inert going overhead"),
    "p": spec("-", 0.05, 0.0, 1.0, "purge fraction of the overhead"),
}


def run(inputs: dict[str, Any] | None = None, series: bool = True) -> dict[str, Any]:
    with np.errstate(all="ignore"):
        return _run(inputs or {}, series)


def _run(inputs: dict[str, Any], series: bool) -> dict[str, Any]:
    values, errors = validate(inputs, SPEC)
    if errors:
        return failed(TEMPLATE, VERSION, errors)
    v = values
    if v["p"] == 0.0 and v["sI"] == 1.0 and v["yI0"] > 0.0:
        msg = "no purge and all inert goes overhead: inert accumulates without bound"
        return failed(TEMPLATE, VERSION, [_err("inert_accumulates", msg, "p")])
    out = envelope(TEMPLATE, VERSION, values, SPEC)
    f0a, f0i = v["F0"] * (1.0 - v["yI0"]), v["F0"] * v["yI0"]
    a, b = _loop_gains(v["Xsp"], v["sA"], v["sI"], v["p"])

    def tear(r: np.ndarray) -> list[float]:  # r = (R_A, R_I) / F0
        return [
            r[0] - a * (f0a / v["F0"] + r[0]),
            r[1] - b * (f0i / v["F0"] + r[1]),
        ]

    sol, _info, ier, _msg = fsolve(tear, [0.0, 0.0], xtol=1e-13, full_output=True)
    ra, ri = float(sol[0] * v["F0"]), float(sol[1] * v["F0"])
    ra_cf = a * f0a / (1.0 - a)
    ri_cf = b * f0i / (1.0 - b) if f0i > 0.0 else 0.0  # b = 1 only if no inert
    scale = max(abs(ra_cf), abs(ri_cf), 1e-300)
    if ier != 1 or max(abs(ra - ra_cf), abs(ri - ri_cf)) > CLOSURE_TOL * scale:
        out["warnings"].append("fsolve differs from closed form; closed form used")
        ra, ri = ra_cf, ri_cf
    rin_a, rin_i = f0a + ra, f0i + ri
    over_a, over_i = v["sA"] * (1 - v["Xsp"]) * rin_a, v["sI"] * rin_i
    prod_a = (1 - v["sA"]) * (1 - v["Xsp"]) * rin_a
    prod_i = (1 - v["sI"]) * rin_i
    prod_b = v["Xsp"] * rin_a
    pa, pi = v["p"] * over_a, v["p"] * over_i
    err_ab = abs(f0a - (prod_a + pa + prod_b)) / f0a if f0a > 0 else 0.0
    err_i = abs(f0i - (prod_i + pi)) / f0i if f0i > 0 else 0.0
    ratio = (ra + ri) / v["F0"]
    if ratio > RATIO_WARN:
        out["warnings"].append(f"very large recycle ratio ({ratio:.0f})")
    flow = "kmol/h"
    out["outputs"] = {
        "reactor_in_A": {"value": rin_a, "unit": flow},
        "reactor_in_I": {"value": rin_i, "unit": flow},
        "R_A": {"value": ra, "unit": flow},
        "R_I": {"value": ri, "unit": flow},
        "R_total": {"value": ra + ri, "unit": flow},
        "P_A": {"value": pa, "unit": flow},
        "P_I": {"value": pi, "unit": flow},
        "P_total": {"value": pa + pi, "unit": flow},
        "prod_A": {"value": prod_a, "unit": flow},
        "prod_B": {"value": prod_b, "unit": flow},
        "prod_I": {"value": prod_i, "unit": flow},
        "X_overall": {"value": (f0a - pa - prod_a) / f0a, "unit": "-"},
        "recycle_ratio": {"value": ratio, "unit": "-"},
        "balance_error": {"value": max(err_ab, err_i), "unit": "-"},
        "yI_reactor_in": {"value": rin_i / (rin_a + rin_i), "unit": "-"},
    }
    out["geometry"] = {
        "type": "flowsheet",
        "units": ["mixer", "reactor", "separator", "splitter"],
    }
    if series:
        out["series"] = _series(v)
    return finish(out)


def _loop_gains(xsp: float, sa: float, si: float, p: Any) -> tuple[Any, Any]:
    """Per-pass recycle fractions of A and I: a = (1-Xsp)*sA*(1-p), b = sI*(1-p)."""
    return (1.0 - xsp) * sa * (1.0 - p), si * (1.0 - p)


def _series(v: Values) -> dict[str, Any]:
    """Closed-form sweeps over the purge fraction (fast, no fsolve)."""
    p = np.geomspace(1e-3, 1.0, N_SERIES)
    a, b = _loop_gains(v["Xsp"], v["sA"], v["sI"], p)
    f0a, f0i = 1.0 - v["yI0"], v["yI0"]  # per unit fresh feed
    rin_a = f0a / (1.0 - a)
    rin_i = f0i / (1.0 - b)
    x_overall = v["Xsp"] * rin_a / f0a
    y_i = rin_i / (rin_a + rin_i)
    return {
        "purge_sweep": series(p, x_overall, "-", "-"),
        "inert_buildup": series(p, y_i, "-", "-"),
    }
