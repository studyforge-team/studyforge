"""Server-side markdown tidy: the web card (remark-math) and the PDF both read answer_md."""

import re

_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$", re.DOTALL)
_BLOCK = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_INLINE = re.compile(r"\\\((.*?)\\\)", re.DOTALL)
# ponytail: literal "\n" + lowercase is left alone (could be \nabla/\nu); outside maths
# the model only ever meant a line break before **Steps:**, "- ", digits or a capital.
_LITERAL_NL = re.compile(r"\\n(?=[A-Z*\-\d\s]|$)")


def tidy_markdown(md: str) -> str:
    md = _BLOCK.sub(lambda m: f"$${m.group(1)}$$", md)
    md = _INLINE.sub(lambda m: f"${m.group(1).strip()}$", md)
    out, last = [], 0
    for m in _MATH.finditer(md):
        out.append(_LITERAL_NL.sub("\n", md[last : m.start()]))
        out.append(m.group())
        last = m.end()
    out.append(_LITERAL_NL.sub("\n", md[last:]))
    return "".join(out)
