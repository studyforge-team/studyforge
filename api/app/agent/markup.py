"""Server-side markdown tidy: the web card (remark-math) and the PDF both read answer_md."""

import re

# "$" right before a literal "\n" + text is a stray one ("...$.$\nE = ..."): it must not open
# maths and swallow the line break
_MATH = re.compile(r"\$\$.*?\$\$|\$(?!\\n[A-Z*\-\d\s=])[^$\n]*\$", re.DOTALL)
_BLOCK = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_INLINE = re.compile(r"\\\((.*?)\\\)", re.DOTALL)
# outside maths a literal "\n" is a line break unless it starts a LaTeX command (\nabla, \nu, \neq...)
_LITERAL_NL = re.compile(r"\\n(?!(?:abla|u|e|eq|ewline|ot|i)\b)")
_SYMBOLS = {
    "cdot": "·", "times": "×", "mu": "μ", "rho": "ρ", "Delta": "Δ", "pi": "π",
    "approx": "≈", "le": "≤", "ge": "≥", "alpha": "α", "beta": "β", "eta": "η",
    "lambda": "λ", "tau": "τ", "nu": "ν", "sigma": "σ", "theta": "θ",
}  # fmt: skip
_LATEX = re.compile(r"\\{1,2}(" + "|".join(_SYMBOLS) + r")\b")
_TEXT = re.compile(r"(?:\\+ )?\\+(?:text|mathrm)\{([^{}]*)\}")


def _plain(s: str) -> str:
    s = _TEXT.sub(r"\1", _LITERAL_NL.sub("\n", s))
    return _LATEX.sub(lambda m: _SYMBOLS[m.group(1)], s)


def tidy_markdown(md: str) -> str:
    md = _BLOCK.sub(lambda m: f"$${m.group(1)}$$", md)
    md = _INLINE.sub(lambda m: f"${m.group(1).strip()}$", md)
    out, last = [], 0
    for m in _MATH.finditer(md):
        out.append(_plain(md[last : m.start()]))
        out.append(m.group())
        last = m.end()
    out.append(_plain(md[last:]))
    return "".join(out)
