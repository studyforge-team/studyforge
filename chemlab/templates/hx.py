"""Heat exchanger template: size an exchanger for a given duty (constant cp, no phase change).

Duty and cold outlet from the energy balance, with Ch = mh*cph and Cc = mc*cpc (W/K):
    Q = Ch (Th_in - Th_out),   Tc_out = Tc_in + Q / Cc

Area by LMTD, A = Q / (U F LMTD), for three flow arrangements:
    counter-flow   LMTD from (Th_in - Tc_out, Th_out - Tc_in), F = 1
    co-current     LMTD from (Th_in - Tc_in, Th_out - Tc_out), F = 1
    1-2 shell-and-tube (1 shell pass, 2 tube passes): counter-flow LMTD times
        F = S ln((1-P)/(1-RP)) / ((R-1) ln((2-P(R+1-S)) / (2-P(R+1+S))))
        R = (Th_in-Th_out)/(Tc_out-Tc_in), P = (Tc_out-Tc_in)/(Th_in-Tc_in), S = sqrt(R^2+1)
        R = 1:  F = (S P/(1-P)) / ln((2-P(2-S)) / (2-P(2+S)))
Near Cr = 1 (R = 1) the textbook forms are 0/0; every such ratio is evaluated as
x / ln(1 + x) with the small difference x computed directly (no cancellation).
The same three areas are computed again by e-NTU (A = NTU Cmin / U, eps = Q / Qmax) as an
independent check; a disagreement above 1e-6 is reported as a warning.

Feasibility: counter-flow needs Th_out > Tc_in and Th_in > Tc_out, otherwise nothing works
(error). Co-current needs Th_out > Tc_out; the 1-2 exchanger needs 2 - P(R+1+S) > 0.
Either one failing is a warning and its outputs are left out. F < 0.75 is warned (usual
design rule: use more shells in series).

Profile (series): counter-flow temperatures along the fraction of area from the hot-inlet
end, Th - Tc = (Th_in - Tc_out) exp(-U A x (1/Ch - 1/Cc)) (linear when Ch = Cc).

Geometry (for the 2D drawing), from the 1-2 area: tubes of outer diameter do and length Lt,
n_tubes = ceil(A / (pi do Lt)) rounded up to even (2 passes), triangular pitch 1.25 do,
bundle diameter Db = do (n_tubes / 0.249)^(1/2.207) (Coulson & Richardson vol. 6,
eq. 12.3b, 2 passes). Shell diameter = Db + 15 mm clearance: illustrative (fixed
tube-sheet bundles need about 10-20 mm). Which fluid goes in the shell is not decided.
"""

import math
from typing import Any

import numpy as np

from ._common import InputSpec, _err, envelope, failed, finish, series, spec, validate

TEMPLATE = "hx"
VERSION = "1.0"
N_SERIES = 60
F_MIN = 0.75
K1, N1 = 0.249, 2.207  # bundle constants: triangular pitch 1.25 do, 2 tube passes
CLEARANCE = 0.015  # m, shell inner diameter minus bundle diameter (illustrative)

SPEC: dict[str, InputSpec] = {
    "mh": spec("kg/s", 2.0, 1e-4, 1e4, "hot stream mass flow"),
    "cph": spec("J/(kg K)", 2100.0, 100.0, 1e5, "hot stream heat capacity"),
    "Th_in": spec("K", 433.15, 200.0, 1500.0, "hot inlet temperature"),
    "Th_out": spec(
        "K", 373.15, 200.0, 1500.0, "hot outlet temperature (sets the duty)"
    ),
    "mc": spec("kg/s", 2.5, 1e-4, 1e4, "cold stream mass flow"),
    "cpc": spec("J/(kg K)", 4180.0, 100.0, 1e5, "cold stream heat capacity"),
    "Tc_in": spec("K", 293.15, 200.0, 1500.0, "cold inlet temperature"),
    "U": spec("W/(m^2 K)", 350.0, 1.0, 1e5, "overall heat transfer coefficient"),
    "do": spec("m", 0.01905, 0.005, 0.1, "tube outer diameter (drawing)"),
    "Lt": spec("m", 4.88, 0.5, 20.0, "tube length (drawing)"),
}


def run(inputs: dict[str, Any] | None = None, series: bool = True) -> dict[str, Any]:
    with np.errstate(all="ignore"):
        return _run(inputs or {}, series)


def _xlog(x: float) -> float:
    """x / ln(1 + x), accurate near x = 0 (where both parts vanish)."""
    if abs(x) < 1e-5:
        return 1 + x / 2 - x * x / 12
    return x / math.log1p(x)


def lmtd(d1: float, d2: float, diff: float) -> float:
    """Log-mean of d1, d2 with d1 - d2 = diff passed in exactly (no cancellation)."""
    return d2 * _xlog(diff / d2)


def f_12(rm1: float, p: float) -> float | None:
    """F for 1 shell pass, 2 tube passes, with rm1 = R - 1 (stable at R = 1).
    None when no such exchanger can do the duty."""
    r = 1 + rm1
    s = math.sqrt(r * r + 1)
    den = 2 - p * (r + 1 + s)
    g = rm1 * p / (1 - p)  # ln((1-P)/(1-RP)) / (R-1) = (P/(1-P)) / _xlog(-g)
    if den <= 0 or p >= 1 or g >= 1:
        return None
    return s * (p / (1 - p)) / _xlog(-g) / math.log((2 - p * (r + 1 - s)) / den)


def ntu(kind: str, eps: float, cr: float, one_minus_cr: float) -> float:
    """NTU from effectiveness (inverse e-NTU relations), stable at Cr = 1."""
    if kind == "counter":  # ln((1-eps Cr)/(1-eps)) / (1-Cr)
        y = eps * one_minus_cr / (1 - eps)
        return eps / (1 - eps) / _xlog(y)
    if kind == "co":
        return -math.log(1 - eps * (1 + cr)) / (1 + cr)
    s = math.sqrt(1 + cr * cr)  # 1-2 shell-and-tube
    e = (2 / eps - (1 + cr)) / s
    return -math.log((e - 1) / (e + 1)) / s


def _run(inputs: dict[str, Any], want_series: bool) -> dict[str, Any]:
    p, errors = validate(inputs, SPEC)
    if not errors:
        errors = _check(p)
    if errors:
        return failed(TEMPLATE, VERSION, errors)
    out = envelope(TEMPLATE, VERSION, p, SPEC)
    warn = out["warnings"]
    ch, cc = p["mh"] * p["cph"], p["mc"] * p["cpc"]
    q = ch * (p["Th_in"] - p["Th_out"])
    tco = p["Tc_in"] + q / cc
    cmin, cmax = min(ch, cc), max(ch, cc)
    cr, one_minus_cr = cmin / cmax, (cmax - cmin) / cmax
    eps = q / (cmin * (p["Th_in"] - p["Tc_in"]))
    dth = p["Th_in"] - p["Th_out"]
    # counter-flow end differences differ by dth (1 - Ch/Cc): passed exactly, not subtracted
    lm_ct = lmtd(p["Th_in"] - tco, p["Th_out"] - p["Tc_in"], dth * (cc - ch) / cc)
    o: dict[str, tuple[float, str]] = {
        "Q": (q, "W"),
        "Tc_out": (tco, "K"),
        "Ch": (ch, "W/K"),
        "Cc": (cc, "W/K"),
        "effectiveness": (eps, "-"),
        "LMTD_counter": (lm_ct, "K"),
        "A_counter": (q / (p["U"] * lm_ct), "m^2"),
    }
    if p["Th_out"] > tco:
        lm_co = lmtd(p["Th_in"] - p["Tc_in"], p["Th_out"] - tco, dth + q / cc)
        o["LMTD_co"] = (lm_co, "K")
        o["A_co"] = (q / (p["U"] * lm_co), "m^2")
    else:
        warn.append(
            "co-current is impossible here: the cold outlet would pass the hot outlet"
        )
    r_, p_ = cc / ch, (tco - p["Tc_in"]) / (p["Th_in"] - p["Tc_in"])  # R = Cc/Ch
    f = f_12((cc - ch) / ch, p_)
    if f is not None and f > 0:
        o["R"], o["P"], o["F"] = (r_, "-"), (p_, "-"), (f, "-")
        o["A_shell12"] = (q / (p["U"] * f * lm_ct), "m^2")
        if f < F_MIN:
            warn.append(f"F below 0.75 ({f:.3f}): use two or more shells in series")
    else:
        warn.append(
            "a 1-2 shell-and-tube exchanger cannot do this duty (temperature cross)"
        )
    for kind, key in (
        ("counter", "A_counter"),
        ("co", "A_co"),
        ("shell12", "A_shell12"),
    ):
        if key in o:
            a_ntu = ntu(kind, eps, cr, one_minus_cr) * cmin / p["U"]
            if not math.isclose(a_ntu, o[key][0], rel_tol=1e-6):
                warn.append(
                    f"LMTD and e-NTU disagree for {kind}: {o[key][0]:.6g} vs {a_ntu:.6g} m^2"
                )
    o["NTU_counter"] = (o["A_counter"][0] * p["U"] / cmin, "-")
    if "A_shell12" in o:
        out["geometry"] = _geometry(o["A_shell12"][0], p["do"], p["Lt"])
        o["A_installed"] = (
            out["geometry"]["n_tubes"] * math.pi * p["do"] * p["Lt"],
            "m^2",
        )
    out["outputs"] = {k: {"value": v, "unit": u} for k, (v, u) in o.items()}
    if want_series:
        x = np.linspace(0.0, 1.0, N_SERIES)
        d0 = p["Th_in"] - tco
        k = (cc - ch) / cc
        if k == 0:
            qx = dth * x
        else:  # Th - Tc = d0 exp(-c x); hot-side drop = (d0 - (Th - Tc)) / k, via expm1
            c = p["U"] * o["A_counter"][0] * (cc - ch) / (ch * cc)
            qx = -d0 * np.expm1(-c * x) / k
        out["series"] = {
            "hot_profile": series(x, p["Th_in"] - qx, "-", "K"),
            "cold_profile": series(x, tco - qx * ch / cc, "-", "K"),
        }
    return finish(out)


def _check(p: dict[str, float]) -> list[dict[str, str]]:
    if p["Th_out"] >= p["Th_in"]:
        return [_err("no_cooling", "Th_out must be below Th_in", "Th_out")]
    if p["Tc_in"] >= p["Th_in"]:
        return [_err("hot_not_hotter", "Tc_in must be below Th_in", "Tc_in")]
    tco = p["Tc_in"] + p["mh"] * p["cph"] * (p["Th_in"] - p["Th_out"]) / (
        p["mc"] * p["cpc"]
    )
    if p["Th_out"] <= p["Tc_in"] or tco >= p["Th_in"]:
        msg = (
            f"temperature cross: cold outlet {tco:.1f} K, hot outlet {p['Th_out']:.1f} K;"
            " no exchanger can do this duty (raise Th_out or the cold flow)"
        )
        return [_err("temperature_cross", msg, "Th_out")]
    return []


def _geometry(area: float, do: float, lt: float) -> dict[str, Any]:
    n = math.ceil(area / (math.pi * do * lt))
    n += n % 2
    db = do * (n / K1) ** (1 / N1)
    return {
        "type": "shell_and_tube",
        "shell_passes": 1,
        "tube_passes": 2,
        "n_tubes": n,
        "tube_od_m": do,
        "tube_length_m": lt,
        "pitch_m": 1.25 * do,
        "layout": "triangular",
        "bundle_diameter_m": db,
        "shell_diameter_m": db + CLEARANCE,
    }
