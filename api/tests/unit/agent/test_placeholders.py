import pytest

from app.agent.loop import _has_placeholder


@pytest.mark.parametrize(
    "md",
    [
        r"$$$ P = {<number>}{\,\text{kPa}}$$$",
        r"**Answer:** $\mathbf{{<final_number>}}{\ \text{kPa}}$",
        "{<value>}",
        "P = <number> kPa",
    ],
)
def test_placeholders_are_detected(md: str) -> None:
    assert _has_placeholder(md)


@pytest.mark.parametrize(
    "md",
    [
        "$x < 5$",
        "a<b",
        "if a<b and c>d",
        "Re < 2300 so laminar",
        "$$a=b$$",
        "P = 2500 kPa",
    ],
)
def test_ordinary_text_is_not_a_placeholder(md: str) -> None:
    assert not _has_placeholder(md)


@pytest.mark.parametrize("md", ["<unit>", "<item>", "<b_value>", "<pressure_drop>", "{<value>}"])
def test_other_tags_still_flagged(md: str) -> None:
    assert _has_placeholder(md)


@pytest.mark.parametrize("md", ["a<br>b", "x<sub>f</sub>", "10<sup>5</sup>"])
def test_tags_tidy_rewrites_are_not_placeholders(md: str) -> None:
    assert not _has_placeholder(md)
