"""Every method card that says `tool(...) returns a, b, c` must match how that chemlab tool
unpacks. Models unpack exactly what the card lists; a mismatch is a ValueError in the
sandbox (27 Oct: cubic_eos was carded with 6 values but unpacked to 4, so the independent
re-solve of a correct Lee/Kesler answer crashed twice and the student got no number)."""

import importlib.util
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

from app.agent import prompts

ROOT = Path(__file__).resolve().parents[4]


def _correlations() -> Any:
    spec = importlib.util.spec_from_file_location(
        "chemlab_correlations", ROOT / "chemlab" / "templates" / "_correlations.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = _correlations()


def _benzene(t: float) -> float:
    return 10 ** (6.90565 - 1211.033 / (t + 220.79))  # mmHg, degC


def _toluene(t: float) -> float:
    return 10 ** (6.95464 - 1344.8 / (t + 219.482))


PSAT = [_benzene, _toluene]
SAMPLES: dict[str, tuple[tuple, dict]] = {
    "lee_kesler": ((1.2, 0.66, 0.0), {}),
    "pitzer_virial": ((1.2, 0.3, 0.0), {}),
    "ig_cp_integrals": ((300.0, 400.0, 1.0, 1e-3), {}),
    "gamma_binary": (("margules", 0.4, (1.0, 0.5)), {}),
    "cubic_eos": ((300.0, 1e5, 369.8, 42.48e5, 0.152), {}),
    "cubic_psat": ((300.0, 369.8, 42.48e5, 0.152), {}),
    "bubble_p": (([0.4, 0.6], [100.0, 50.0]), {}),
    "dew_p": (([0.4, 0.6], [100.0, 50.0]), {}),
    "bubble_t": (([0.4, 0.6], 760.0, PSAT), {"T0": 80.0}),
    "dew_t": (([0.4, 0.6], 760.0, PSAT), {"T0": 80.0}),
}
PROPS_TOOLS = sorted(
    n
    for n, f in vars(C).items()
    if inspect.isfunction(f) and not n.startswith("_")
    and inspect.signature(f).return_annotation in (C.Props, "Props")
)
CARDS = " ".join(card for _, card in prompts._CARDS)


def _strip_parens(s: str) -> str:
    while (t := re.sub(r"\([^()]*\)", "", s)) != s:
        s = t
    return s


def card_claim(name: str, keys: set[str]) -> list[str] | None:
    """The names the cards say `name(...)` returns, in order (None if no claim)."""
    m = re.search(rf"\b{name}\(", CARDS)
    if not m:
        return None
    start = max(CARDS.rfind(";", 0, m.start()), CARDS.rfind(". ", 0, m.start())) + 1
    seg = re.split(r";|\.(?:\s|$)", CARDS[start:], maxsplit=1)[0]  # the whole clause
    parts = re.split(r"\breturns?\b", seg, maxsplit=1)
    if len(parts) < 2:
        return None
    head, tail = parts
    callers = re.findall(r"(\w+)\(", head)  # "a(...) and b(...) return X / Y"
    alts = _strip_parens(tail).split("/")
    claim = alts[callers.index(name)] if len(alts) == len(callers) else alts[0]
    out: list[str] = []
    for tok in re.split(r"\s*(?:,|\band\b)\s*", claim.strip()):
        words = tok.split()
        if not words or words[0] not in keys:
            break
        out.append(words[0])
        if len(words) > 1:
            break
    return out


def test_every_props_tool_has_a_sample() -> None:
    assert PROPS_TOOLS and set(PROPS_TOOLS) <= set(SAMPLES), set(PROPS_TOOLS) - set(SAMPLES)


@pytest.mark.parametrize("name", PROPS_TOOLS)
def test_card_lists_what_the_tool_unpacks_to(name: str) -> None:
    args, kw = SAMPLES[name]
    r = getattr(C, name)(*args, **kw)
    claim = card_claim(name, set(r.keys()))  # iter(r) gives the values, not the names
    assert claim is not None, f"no card says what {name} returns"
    assert claim == list(r._main), f"card says {name} returns {claim}, it unpacks to {list(r._main)}"
    assert len(list(r)) == len(claim)  # `a, b, ... = name(...)` with the card's names works
