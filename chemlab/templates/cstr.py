"""CSTR template: liquid phase, constant density, A -> products, rate k(T)*CA^n.

Mole balance:   v0*(CA0 - CA) = V*k(T)*CA^n,  k(T) = k0*exp(-Ea/(R*T))
Energy balance: (-dHr)*v0*CA0*X = rho_cp*v0*(T - T0) + UA*(T - Ta)   (UA = 0: adiabatic)

Method (no division by dHr, no inner root-solve for any order n):
- Scan conversion X. The mole balance gives k = X / (tau*CA0^(n-1)*(1-X)^n), so the
  temperature on the mole-balance curve is explicit: T_MB(X) = Ea / (R*ln(k0/k)).
- Steady states are the roots of the heat residual G - R along that curve
  (G = heat generated, R = heat removed), found on a dense grid and refined with brentq.
- Stability uses both conditions on the transient model's 2x2 Jacobian (CA, T):
  det > 0, which is the slope condition dR/dT > dG/dT, and trace < 0. A state that
  passes only the slope condition is unstable and the reactor oscillates (limit
  cycle); outputs then carry a warning.
- isothermal = 1: T = T0, the energy balance is not used.
- The reported operating point (outputs) is the lowest-temperature stable steady
  state, the one a start-up from the feed temperature reaches; all states are listed
  in steady_states.
"""

import math
from typing import Any

import numpy as np
from scipy.optimize import brentq

from ._common import InputSpec, Values, envelope, failed, finish, series, spec, validate

TEMPLATE = "cstr"
VERSION = "1.1"
R_GAS = 8.314462618  # J/(mol K)
N_SERIES = 150

SPEC: dict[str, InputSpec] = {
    "CA0": spec("mol/m^3", 2000.0, 1e-6, 1e5, "feed concentration of A"),
    "v0": spec("m^3/s", 0.01, 1e-9, 1e3, "volumetric feed flow"),
    "V": spec("m^3", 1.0, 1e-9, 1e5, "reactor volume"),
    "n": spec("-", 1.0, 0.0, 4.0, "reaction order in A"),
    "k0": spec("(m^3/mol)^(n-1)/s", 1.0e10, 1e-30, 1e30, "pre-exponential factor"),
    "Ea": spec("J/mol", 8.0e4, 0.0, 5e5, "activation energy"),
    "dHr": spec("J/mol", -2.0e5, -1e7, 1e7, "heat of reaction (negative = exothermic)"),
    "rho_cp": spec("J/(m^3 K)", 4.18e6, 1.0, 1e8, "volumetric heat capacity"),
    "UA": spec(
        "W/K", 0.0, 0.0, 1e9, "heat transfer coefficient x area (0 = adiabatic)"
    ),
    "Ta": spec("K", 300.0, 1.0, 2000.0, "coolant temperature"),
    "T0": spec("K", 300.0, 1.0, 2000.0, "feed temperature"),
    "isothermal": spec(
        "-", 0.0, 0.0, 1.0, "1 = hold T at T0 and skip the energy balance"
    ),
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
    tau = p["V"] / p["v0"]
    iso = p["isothermal"] >= 0.5
    if iso or p["Ea"] == 0.0:
        # k does not depend on T: X follows from the mole balance alone
        T_fix = p["T0"]
        X, u = _x_isothermal(_k(p, T_fix) * tau * p["CA0"] ** (p["n"] - 1), p["n"])
        T = T_fix if iso else float(_t_energy(p, X))
        states = [_state(p, tau, T, X, stable=True, u=u)]
    else:
        states = _steady_states(p, tau)
    if not states:
        out.update(ok=False)
        out["errors"].append(
            {"code": "no_steady_state", "message": "no steady state found", "field": ""}
        )
        return finish(out)

    op = next((s for s in states if s["stable"]), states[0])
    out["steady_states"] = states
    out["n_steady_states"] = len(states)
    if not any(s["stable"] for s in states):
        out["warnings"].append(
            "no stable steady state: the reactor oscillates (limit cycle) instead of"
            " settling; outputs show an unstable state"
        )
    if len(states) > 1:
        out["warnings"].append(
            f"{len(states)} steady states; outputs show the lowest-temperature stable one"
        )
    out["outputs"] = {
        "tau": {"value": tau, "unit": "s"},
        "X": {"value": op["X"], "unit": "-"},
        "X_percent": {"value": 100.0 * op["X"], "unit": "%"},
        "T": {"value": op["T"], "unit": "K"},
        "T_C": {"value": op["T"] - 273.15, "unit": "degC"},
        "CA": {"value": op["CA"], "unit": "mol/m^3"},
        "Da": {"value": op["Da"], "unit": "-"},
        "rate": {"value": op["rate"], "unit": "mol/(m^3 s)"},
    }
    if not iso:
        out["outputs"]["dT_adiabatic"] = {"value": _dt_ad(p), "unit": "K"}
    d = (4.0 * p["V"] / math.pi) ** (1.0 / 3.0)  # H = D
    out["geometry"] = {
        "type": "cstr",
        "volume_m3": p["V"],
        "diameter_m": d,
        "height_m": d,
    }
    if series:
        out["series"] = _series(p, tau, op["T"], iso)
    return finish(out)


def _k(p: Values, T: Any) -> Any:
    return p["k0"] * np.exp(-p["Ea"] / (R_GAS * T))


def _dt_ad(p: Values) -> float:
    return -p["dHr"] * p["CA0"] / p["rho_cp"]


def _x_isothermal(da: float, n: float) -> tuple[float, float]:
    """(X, 1 - X) solving X = Da*(1-X)^n on [0, 1]. The root is unique (left side
    rises, right side falls); it is found in X when X <= 0.5 and in u = 1 - X
    otherwise, so conversions near 1 keep full precision."""
    if da <= 0.0:
        return 0.0, 1.0
    if n == 0.0:
        return (1.0, 0.0) if da >= 1.0 else (da, 1.0 - da)
    if 0.5 - da * 0.5**n >= 0.0:
        x = float(brentq(lambda x: x - da * (1.0 - x) ** n, 0.0, 0.5, xtol=1e-300))
        return x, 1.0 - x
    u = float(brentq(lambda u: (1.0 - u) - da * u**n, 0.0, 0.5, xtol=1e-300))
    return 1.0 - u, u


def _t_energy(p: Values, X: Any) -> Any:
    """Temperature from the energy balance at conversion X (explicit, linear in X)."""
    a = p["rho_cp"] * p["v0"]
    return (-p["dHr"] * p["v0"] * p["CA0"] * X + a * p["T0"] + p["UA"] * p["Ta"]) / (
        a + p["UA"]
    )


def _ln_ratio(p: Values, tau: float, X: Any, u: Any) -> Any:
    """ln(k0/k) for the k the mole balance needs at conversion X (u = 1 - X)."""
    ln_k = (
        np.log(X)
        - math.log(tau)
        - (p["n"] - 1) * math.log(p["CA0"])
        - p["n"] * np.log(u)
    )
    return math.log(p["k0"]) - ln_k


def _t_mole_balance(p: Values, tau: float, X: Any, u: Any) -> Any:
    """T on the mole-balance curve at conversion X (u = 1 - X, passed separately so
    it keeps full precision near complete conversion). NaN where k >= k0."""
    ln_ratio = _ln_ratio(p, tau, np.asarray(X, dtype=float), u)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ln_ratio > 0, p["Ea"] / (R_GAS * ln_ratio), np.nan)


def _residual(p: Values, tau: float, X: Any, u: Any) -> Any:
    """Heat generated minus heat removed along the mole-balance curve (W)."""
    T = _t_mole_balance(p, tau, X, u)
    gen = -p["dHr"] * p["v0"] * p["CA0"] * np.asarray(X, dtype=float)
    removed = p["rho_cp"] * p["v0"] * (T - p["T0"]) + p["UA"] * (T - p["Ta"])
    return gen - removed


def _steady_states(p: Values, tau: float) -> list[dict[str, Any]]:
    # Scan X on [1e-300, 0.5] and u = 1 - X on [1e-300, 0.5]; each half is solved in
    # its own small variable so both ends keep full relative precision.
    small = np.geomspace(1e-300, 0.5, 6000)  # ~20 points per decade
    halves = [
        (lambda t: (t, 1.0 - t)),  # t = X
        (lambda t: (1.0 - t, t)),  # t = u
    ]
    roots: list[tuple[float, float]] = []
    for to_xu in halves:
        f = _residual(p, tau, *to_xu(small))

        def f1(t: float, to_xu: Any = to_xu) -> float:
            return float(_residual(p, tau, *to_xu(t)))

        def ln_r(t: float, to_xu: Any = to_xu) -> float:
            return float(_ln_ratio(p, tau, *to_xu(t)))

        ok = np.isfinite(f)
        with np.errstate(invalid="ignore"):
            change = (ok[:-1] & ok[1:] & (f[:-1] * f[1:] <= 0.0)) | (ok[:-1] != ok[1:])
        for i in np.flatnonzero(change):
            a, b = float(small[i]), float(small[i + 1])
            if ok[i] and ok[i + 1]:
                if f[i] == 0.0:
                    roots.append(to_xu(a))
                elif f[i] * f[i + 1] < 0.0:
                    roots.append(to_xu(float(brentq(f1, a, b, xtol=1e-300))))
            elif ok[i] != ok[i + 1] and f[i if ok[i] else i + 1] > 0.0:
                # T -> infinity at the edge where the needed k reaches k0, so the
                # residual drops to -infinity there: a root hides near that edge.
                edge = float(brentq(ln_r, a, b, xtol=1e-300))
                inside = a if ok[i] else b
                t = _approach_negative(f1, inside, edge)
                if t is not None:
                    roots.append(to_xu(float(brentq(f1, inside, t, xtol=1e-300))))
    states = {}
    for X, u in roots:
        T = float(_t_mole_balance(p, tau, X, u))
        states[round(T, 9)] = _state(p, tau, T, X, stable=_stable(p, tau, T, X, u), u=u)
    if p["n"] == 0.0:
        # Zero order can finish (X = 1) at a finite T, so the residual need not change
        # sign: full conversion is a steady state when k*tau >= CA0 at the
        # energy-balance temperature for X = 1. It is stable (dG/dT = 0 there).
        T1 = float(_t_energy(p, 1.0))
        if T1 > 0.0 and float(_k(p, T1)) * tau >= p["CA0"]:
            states[round(T1, 9)] = _state(p, tau, T1, 1.0, stable=True, u=0.0)
    return [states[k] for k in sorted(states)]  # a root at X = 0.5 is found twice


def _stable(p: Values, tau: float, T: float, X: float, u: float) -> bool:
    """Both Jacobian conditions for the transient model
    dCA/dt = (CA0 - CA)/tau - r,  rho_cp*V*dT/dt = rho_cp*v0*(T0 - T) - UA*(T - Ta) - dHr*V*r
    with r = k(T)*CA^n. Written with X and u = 1 - X so nothing divides by CA."""
    # slope condition (det > 0): removal line steeper than the generation curve
    dT_dX = R_GAS * T * T / p["Ea"] * (1.0 / X + p["n"] / u)
    dG_dT = -p["dHr"] * p["v0"] * p["CA0"] / dT_dX
    dR_dT = p["rho_cp"] * p["v0"] + p["UA"]
    # trace < 0; r = CA0*X/tau at steady state, dr/dCA = n*r/CA, dr/dT = r*Ea/(R*T^2)
    r = p["CA0"] * X / tau
    a11 = -1.0 / tau - p["n"] * r / (p["CA0"] * u)
    a22 = (-dR_dT - p["dHr"] * p["V"] * r * p["Ea"] / (R_GAS * T * T)) / (
        p["rho_cp"] * p["V"]
    )
    return bool(dR_dT > dG_dT and a11 + a22 < 0.0)


def _approach_negative(f: Any, inside: float, edge: float) -> float | None:
    """A point between inside and edge, close to edge, where f < 0 (f(inside) > 0)."""
    for k in range(1, 60):
        t = edge + (inside - edge) * 0.5**k
        v = f(t)
        if math.isfinite(v) and v < 0.0:
            return t
    return None


def _state(
    p: Values, tau: float, T: float, X: float, stable: bool, u: float | None = None
) -> dict[str, Any]:
    k = float(_k(p, T))
    ca = p["CA0"] * (1.0 - X if u is None else u)
    return {
        "T": float(T),
        "X": float(X),
        "CA": ca,
        "Da": k * tau * p["CA0"] ** (p["n"] - 1),
        # consumption rate from the mole balance; equals k*CA^n except when a
        # zero-order reaction has used up all of A
        "rate": p["CA0"] * X / tau,
        "stable": stable,
    }


def _series(p: Values, tau: float, T_op: float, iso: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    X = np.linspace(1e-3, 0.999, N_SERIES)
    # S-curve: conversion against residence time, every branch (X parametrises it)
    T_X = np.full_like(X, p["T0"]) if iso else _t_energy(p, X)
    tau_X = X / (_k(p, T_X) * p["CA0"] ** (p["n"] - 1) * (1.0 - X) ** p["n"])
    out["s_curve"] = series(tau_X, X, "s", "-")
    # Levenspiel plot at the operating temperature: CSTR volume = v0*CA0*X/(-rA)
    Xl = np.linspace(0.0, 0.95, N_SERIES)
    inv_rate = 1.0 / (float(_k(p, T_op)) * (p["CA0"] * (1.0 - Xl)) ** p["n"])
    out["levenspiel"] = series(Xl, inv_rate, "-", "m^3 s/mol")
    if not iso:
        lo_t = min(p["T0"], p["Ta"])
        hi_t = max(p["T0"], p["Ta"]) + abs(_dt_ad(p))
        T = np.linspace(lo_t, hi_t + 0.05 * (hi_t - lo_t) + 1.0, N_SERIES)
        da = _k(p, T) * tau * p["CA0"] ** (p["n"] - 1)
        X_T = np.array([_x_isothermal(float(d), p["n"])[0] for d in da])
        gen = -p["dHr"] * p["v0"] * p["CA0"] * X_T
        removed = p["rho_cp"] * p["v0"] * (T - p["T0"]) + p["UA"] * (T - p["Ta"])
        out["heat_generated"] = series(T, gen, "K", "W")
        out["heat_removed"] = series(T, removed, "K", "W")
    return out
