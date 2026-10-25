"""Pure routing guards for the agent loop (WP6, WP7). Stdlib only."""

import re

_DERIVE_VERB = re.compile(
    # "draw"/"sketch" stay on the calc route: only it has the draw_diagram tool
    r"\b(derive|derivation|prove|show\s+that|obtain\s+an?\s+(?:expression|equation|relation))\b",
    re.IGNORECASE,
)
# digits that are not data: ordinals (2nd law), 1D/2-D, and digits glued to letters
# (subscripts such as C_A0, x1, k2).
_NOT_A_VALUE = re.compile(
    r"\b\d+(?:st|nd|rd|th)\b|\b\d+-?[dD]\b|[A-Za-z_]\d+|\d+[A-Za-z]*\^?\{?\d*\}?(?=[A-Za-z])",
)
_NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?(?![\w])")


def is_derivation(question: str) -> bool:
    """True for derive/prove/show-that questions that give nothing to compute."""
    if not _DERIVE_VERB.search(question):
        return False
    return not _NUMBER.search(_NOT_A_VALUE.sub(" ", question))


_ENG_WORDS = re.compile(
    r"(?<![\w])(?:m\^?2/s|kPa|bar|mol|kg|L/min)(?![\w])"
    r"|\b(?:diffusivity|viscosity|reactor|CSTR|PFR|distillation|heat\s+exchanger"
    r"|correlation|enthalpy|entropy|Reynolds|Nusselt|Prandtl|NPSH|conversion"
    r"|equilibrium|fugacity|flash|absorption|Antoine|Wilke)\b",
    re.IGNORECASE,
)
# short units: case matters ("K" kelvin, not the letter k)
_ENG_UNITS = re.compile(r"(?<![\w])(?:K|J|Pa|W/m)(?![\w])|°\s?C")


def has_eng_signal(question: str) -> bool:
    """True when the text carries an engineering unit or term (word-bounded)."""
    return bool(_ENG_WORDS.search(question) or _ENG_UNITS.search(question))
