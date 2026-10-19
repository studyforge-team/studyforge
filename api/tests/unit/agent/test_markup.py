import re

import pytest

from app.agent.markup import tidy_markdown

_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$", re.DOTALL)

# Real snippets from the live baseline (1019).
CONCEPT = (
    "raises the coefficient \\(h\\).\n\n**Governing equations**\n\n"
    "\\[ \\boxed{\\text{NPSH}_{a}\\; \\ge \\; \\text{NPSH}_{r}} \\]\n\nwhere"
)
CATALYST = "1. **Arrhenius law**\n\n   \\[\n   k = A\\,\\exp\\!\\left(-\\frac{E_a}{RT}\\right)\n   \\]\n"
TABLE = "| \\( \\rho \\) | Air density |\n| \\( \\mu \\) | Dynamic viscosity |"
CALC = (
    "**Given:** Area $ A = 10 \\, \\text{m}^2 $.\\n**Method:** Use Fourier's law: "
    "$ Q = \\frac{k A \\Delta T}{L} $.\\n**Steps:** First multiply."
)
CALC2 = "Voltage $V = 12$. \\n**Method:** Parallel.\\nRadius = 25 mm,\\nArea = 3\\nThen done"


@pytest.mark.parametrize("src", [CONCEPT, CATALYST, TABLE, CALC, CALC2])
def test_clean_outside_maths_and_idempotent(src: str) -> None:
    out = tidy_markdown(src)
    outside = _MATH.sub("", out)
    assert "\\(" not in outside and "\\[" not in outside
    assert "\\n" not in outside
    assert tidy_markdown(out) == out


def test_delimiters_converted() -> None:
    assert "$h$" in tidy_markdown(CONCEPT)
    assert "$$ \\boxed" in tidy_markdown(CONCEPT)
    assert tidy_markdown(TABLE).startswith("| $\\rho$ | Air density |")


def test_newlines_real() -> None:
    assert tidy_markdown(CALC2).count("\n") == 4


def test_maths_content_untouched() -> None:
    s = "$$\\nabla f$$ and $x = \\left(a\\right) \\bigl[b\\bigr] \\nu \\neq 0$"
    assert tidy_markdown(s) == s
    assert "\\left(" in tidy_markdown(CATALYST)


def test_plain_text_unchanged() -> None:
    s = "**Answer:** about 3.2 MA/m^2.\n\nSee $x^2$ and $$y$$."
    assert tidy_markdown(s) == s


def test_final_answer_is_tidied() -> None:
    # every answer leaves through loop._final, so the web card and the PDF both get it
    from app.agent.loop import _final
    from app.agent.state import SolveState

    state = SolveState(id="s", user_id="u", question="q")
    out = _final(state, r"Rate \(k\) here.\n**Steps:** \[x = 1\]", "medium")
    assert out.answer_md == "Rate $k$ here.\n**Steps:** $$x = 1$$"
