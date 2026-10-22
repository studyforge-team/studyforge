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
