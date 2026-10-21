import json
import re
from pathlib import Path

import pytest

from app.agent.markup import _DOUBLE, _MATH, tidy_markdown

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
    assert tidy_markdown(CALC2).count("\n") == 5  # blank line before **Method:**


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
    assert out.answer_md == "Rate $k$ here.\n\n**Steps:** $$x = 1$$"


FIXTURES = json.loads(
    (Path(__file__).parent / "markup_fixtures.json").read_text("utf-8")
)


def _segs(s: str) -> list[str]:
    return [m.group() for m in _MATH.finditer(s)]


@pytest.mark.parametrize("name", FIXTURES["markup_answers"])
def test_real_answers_have_no_raw_markup_outside_maths(name: str) -> None:
    src = FIXTURES["markup_answers"][name]
    out = tidy_markdown(src)
    outside = _MATH.sub("", out)
    for bad in ("\\n", "\\cdot", "\\mu", "\\times", "\\text{"):
        assert bad not in outside
    assert _segs(out) == _segs(_DOUBLE.sub(lambda _: chr(92), src))


def test_bare_latex_and_text_outside_maths() -> None:
    assert (
        tidy_markdown(r"Q = A \cdot v, (cp \cdot \mu) / k") == "Q = A · v, (cp · μ) / k"
    )
    assert (
        tidy_markdown(r"**3.79\ \text{units}** \Delta T \le 5")
        == "**3.79units** Δ T ≤ 5"
    )
    assert tidy_markdown(r"a.\nb and \nthe end") == "a.\nb and \nthe end"


def test_stray_dollar_before_literal_newline_keeps_the_break_outside_maths() -> None:
    assert tidy_markdown(r"$a$.$\nE = 1$.") == "$a$.$\nE = 1$."


def test_commands_and_maths_left_alone() -> None:
    keep = r"\nabla f, \nu\,x, \neq, \left( x \right), \lefty"
    assert tidy_markdown(keep) == keep.replace(r"\nu", "ν")
    inside = r"$x \le 3 \cdot \mu \text{ m} \nabla$ and $$a \times b\nu$$"
    assert tidy_markdown(inside) == inside


def test_double_backslash_and_sections() -> None:
    b, bb, nl = chr(92), chr(92) * 2, chr(10)
    src = nl.join([
        f"**Given:** $k = 0.1{b} {b}text{{min}}^{{-1}}$.",
        f"**Method:** ${bb}displaystyle X = {bb}frac{{k {bb}tau}}{{1 + k {bb}tau}}$",
        "**Steps:**",
        f"$$[X = k {bb}tau (1 - X)]$$",
        f"**Answer:** ${bb}mathbf{{400{b} {b}text{{L}}}}$",
    ])
    out = tidy_markdown(src)
    assert not re.search(re.escape(bb) + "[A-Za-z]", out)
    assert all(b + c in out for c in ("frac", "tau", "mathbf", "text"))
    assert out.count(nl * 2) == 4
    row = "$$" + b + "begin{aligned} a &= b " + bb + " c &= d " + b + "end{aligned}$$"
    assert tidy_markdown(row) == row
    assert tidy_markdown(f"{bb}[ x {bb}] y") == "$$ x $$ y"
