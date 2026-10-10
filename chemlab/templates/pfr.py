"""PFR template: isothermal, constant-density liquid, A -> products, rate = k*CA^n.

Design equation:  dCA/dtau = -k*CA^n  with tau = V/v0 (residence time plays the role
of batch time), solved in closed form. With Da = k*tau*CA0^(n-1) and m = n - 1:

    CA/CA0 = exp(-Da)                  (n = 1)
    CA/CA0 = (1 + m*Da)^(-1/m)         (n != 1)

For n < 1 the concentration reaches zero at Da = 1/(1 - n) and stays 0 (clamped).
Rate constant: k if k > 0, otherwise k = k0*exp(-Ea/(R*T)). Isothermal, so there is
no energy balance and no steady-state multiplicity (steady_states stays empty).
The helpers below are shared with batch.py (same kinetics, tau <-> t).
"""

import math
from typing import Any

import numpy as np

from ._common import InputSpec, Values, envelope, failed, finish, series, spec, validate

TEMPLATE = "pfr"
VERSION = "1.0"
R_GAS = 8.314462618  # J/(mol K)
N_SERIES = 150
K_UNIT = "(m^3/mol)^(n-1)/s"

# kinetics inputs shared with batch.py
KINETICS_SPEC: dict[str, InputSpec] = {
    "n": spec("-", 1.0, 0.0, 4.0, "reaction order in A"),
    "k": spec(K_UNIT, 0.0, 0.0, 1e30, "rate constant (> 0 overrides k0, Ea, T)"),
    "k0": spec(K_UNIT, 3.0e5, 1e-30, 1e30, "pre-exponential factor"),
    "Ea": spec("J/mol", 5.0e4, 0.0, 5e5, "activation energy"),
    "T": spec("K", 350.0, 200.0, 1000.0, "reactor temperature (isothermal)"),
}

SPEC: dict[str, InputSpec] = {
    "CA0": spec("mol/m^3", 1000.0, 1e-6, 1e5, "feed concentration of A"),
    "v0": spec("m^3/s", 0.001, 1e-9, 1e3, "volumetric feed flow"),
    "V": spec("m^3", 0.2, 1e-9, 1e5, "reactor volume"),
    "D": spec("m", 0.1, 1e-3, 10.0, "tube inner diameter"),
    **KINETICS_SPEC,
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
    k = rate_constant(p)
    length = 4.0 * p["V"] / (math.pi * p["D"] ** 2)
    if k <= 0.0:
        out["warnings"].append("k is zero (no reaction)")
    da = k * tau * p["CA0"] ** (p["n"] - 1.0)
    X = float(conversion(p["n"], da))
    out["outputs"] = {
        "tau": {"value": tau, "unit": "s"},
        "X": {"value": X, "unit": "-"},
        "X_percent": {"value": 100.0 * X, "unit": "%"},
        "CA": {"value": p["CA0"] * float(remaining(p["n"], da)), "unit": "mol/m^3"},
        "length_m": {"value": length, "unit": "m"},
        "k_used": {"value": k, "unit": K_UNIT},
        "T": {"value": p["T"], "unit": "K"},
        "T_C": {"value": p["T"] - 273.15, "unit": "degC"},
    }
    out["geometry"] = {
        "type": "pfr",
        "length_m": length,
        "diameter_m": p["D"],
        "volume_m3": p["V"],
    }
    if series:
        out["series"] = _series(p, k, da, X, length)
    return finish(out)


def rate_constant(p: Values) -> float:
    """k if given (> 0), otherwise the Arrhenius value k0*exp(-Ea/(R*T))."""
    if p["k"] > 0.0:
        return p["k"]
    return float(p["k0"] * math.exp(-p["Ea"] / (R_GAS * p["T"])))


def remaining(n: float, da: Any) -> Any:
    """CA/CA0 after dimensionless time da = k*t*CA0^(n-1), clamped at 0 for n < 1."""
    da = np.asarray(da, dtype=float)
    m = n - 1.0
    if m == 0.0:
        return np.exp(-da)
    arg = m * da
    safe = np.where(arg > -1.0, arg, 0.0)
    return np.where(arg > -1.0, np.exp(-np.log1p(safe) / m), 0.0)


def conversion(n: float, da: Any) -> Any:
    """X = 1 - CA/CA0 in [0, 1]; expm1 keeps first-order accuracy at small da."""
    if n == 1.0:
        return -np.expm1(-np.asarray(da, dtype=float))
    return np.clip(1.0 - remaining(n, da), 0.0, 1.0)


def _series(p: Values, k: float, da: float, X: float, length: float) -> dict[str, Any]:
    n = p["n"]
    out: dict[str, Any] = {}
    frac = np.linspace(0.0, 1.0, N_SERIES)  # z / L
    z = frac * length
    da_z = frac * da
    out["concentration_profile"] = series(
        z, p["CA0"] * remaining(n, da_z), "m", "mol/m^3"
    )
    out["conversion_profile"] = series(z, conversion(n, da_z), "m", "-")
    if k > 0.0:
        # Levenspiel: PFR volume = v0*CA0 * integral dX/(-rA), -rA = k*(CA0*(1-X))^n
        x_max = min(0.95, X)
        Xl = np.linspace(0.0, x_max, N_SERIES)
        inv_rate = 1.0 / (k * (p["CA0"] * (1.0 - Xl)) ** n)
        out["levenspiel"] = series(Xl, inv_rate, "-", "m^3 s/mol")
    return out
