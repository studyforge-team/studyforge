import pytest

from app.llm.reasoning import extract_json, strip_reasoning


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('<think>plan it</think>\n{"a": 1}', '{"a": 1}'),
        ("<think>one</think>A<think>two</think>B", "AB"),
        # template opened the block itself, so only the closing tag arrives
        ("I should add them.</think>\nanswer", "answer"),
        # block cut off by max_tokens: nothing after it is usable
        ("answer <think>still thinking", "answer"),
        ("<think>never finished", ""),
        (None, ""),
    ],
)
def test_strip_reasoning(raw: str | None, clean: str) -> None:
    assert strip_reasoning(raw) == clean


@pytest.mark.parametrize(
    "text",
    [
        '{"x": 2.5}',
        'Here you go:\n```json\n{"x": 2.5}\n```',
        'Sure. {"x": 2.5} Hope that helps.',
        'Note {not json} then {"x": 2.5}',
    ],
)
def test_extract_json(text: str) -> None:
    assert extract_json(text) == {"x": 2.5}


def test_extract_json_fails_without_json() -> None:
    with pytest.raises(ValueError):
        extract_json("no json here")
