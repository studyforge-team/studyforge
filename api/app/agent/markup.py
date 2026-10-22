"""Server-side markdown tidy: the web card (remark-math) and the PDF both read answer_md."""

import re
from decimal import Decimal

# "$" right before a literal "\n" + text is a stray one ("...$.$\nE = ..."): it must not open
# maths and swallow the line break
_MATH = re.compile(r"\$\$.*?\$\$|\$(?!\\n[A-Z*\-\d\s=])[^$\n]*\$", re.DOTALL)
_BLOCK = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_INLINE = re.compile(r"\\\((.*?)\\\)", re.DOTALL)
_DISPLAY = re.compile(r"\$\$.*?\$\$", re.DOTALL)
# outside maths a literal "\n" is a line break unless it starts a LaTeX command (\nabla, \nu, \neq...)
_LITERAL_NL = re.compile(r"\\n(?!(?:abla|u|e|eq|ewline|ot|i)\b)")
# model over-escapes inside JSON: two backslashes before a letter or bracket become one
# (a doubled backslash before whitespace is a real LaTeX row break and stays)
_DOUBLE = re.compile(r"(?<!\\)\\\\(?=[A-Za-z\[\]()])")
# glued **Section:** lines (single newlines) must be separate paragraphs
_SECTION_NL = re.compile(r"(?<!\n)\n(?!\n)(?=\*\*)|(?<=:\*\*)\n(?!\n)")
_SYMBOLS = {
    "cdot": "·", "times": "×", "mu": "μ", "rho": "ρ", "Delta": "Δ", "pi": "π",
    "approx": "≈", "le": "≤", "ge": "≥", "alpha": "α", "beta": "β", "eta": "η",
    "lambda": "λ", "tau": "τ", "nu": "ν", "sigma": "σ", "theta": "θ",
}  # fmt: skip
_LATEX = re.compile(r"\\{1,2}(" + "|".join(_SYMBOLS) + r")\b")
_TEXT = re.compile(r"(?:\\+ )?\\+(?:text|mathrm)\{([^{}]*)\}")


_BR = re.compile(r"<br\s*/?>")
_SUB = re.compile(r"<sub>(.*?)</sub>")
_SUP = re.compile(r"<sup>(.*?)</sup>")
_CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
# float noise: a decimal (optional exponent) not glued to an identifier or a thousands separator
_DECIMAL = re.compile(r"(?<![\w.,])(\d+)\.(\d+)([eE][-+]?\d+)?(?!\.?\d)")


def _round(m: re.Match[str]) -> str:
    whole, frac, exp = m[1], m[2], m[3] or ""
    if len((whole + frac).lstrip("0")) < 9:
        return m.group()
    d = Decimal(f"{whole}.{frac}")
    keep = max(4, len(whole.lstrip("0")))
    out = format(d.quantize(Decimal(1).scaleb(d.adjusted() - keep + 1)), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out + exp


def _plain(s: str) -> str:
    s = _BR.sub("\n\n", _SUB.sub(r"_\1", _SUP.sub(r"^\1", s)))
    s = _TEXT.sub(r"\1", _LITERAL_NL.sub("\n", s))
    s = _SECTION_NL.sub("\n\n", s)
    return _DECIMAL.sub(_round, _LATEX.sub(lambda m: _SYMBOLS[m.group(1)], s))


def tidy_markdown(md: str) -> str:
    out, last = [], 0
    for m in _CODE.finditer(md):  # code is never touched
        out.append(_tidy(md[last : m.start()]))
        out.append(m.group())
        last = m.end()
    out.append(_tidy(md[last:]))
    return "".join(out)


def _tidy(md: str) -> str:
    md = _DOUBLE.sub(lambda _: chr(92), md)
    md = _BLOCK.sub(lambda m: f"$${m.group(1)}$$", md)
    # a stray \( or \) in display maths would pair with a later inline \(...\) and corrupt the text
    # ponytail: also strips the paren of a row break followed by one ("\\(b+c)"); rare, fix if seen
    md = _DISPLAY.sub(lambda m: re.sub(r"\\[()]", "", m.group()), md)
    md = _INLINE.sub(lambda m: f"${m.group(1).strip()}$", md)
    out, last = [], 0
    for m in _MATH.finditer(md):
        out.append(_plain(md[last : m.start()]))
        out.append(_DECIMAL.sub(_round, _BR.sub(" ", m.group())))
        last = m.end()
    out.append(_plain(md[last:]))
    return "".join(out)
