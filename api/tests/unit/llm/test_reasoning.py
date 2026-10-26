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


def test_fix_latex_escapes() -> None:
    from app.llm.reasoning import extract_json
    from app.llm.reasoning import fix_latex_escapes as fx

    bs = chr(92)  # one backslash
    assert fx("\x08egin{aligned}") == bs + "begin{aligned}"
    assert fx("\x0crac{1}{2}") == bs + "frac{1}{2}"
    assert fx("2\times") == "2" + bs + "times"
    assert fx("line one\nThe end") == "line one\nThe end"
    assert fx("$\nabla f$") == "$" + bs + "nabla f$"
    assert fx({"a": ["\x08ar", {"b": "\theta"}]}) == {"a": [bs + "bar", {"b": bs + "theta"}]}
    assert fx(bs + "begin x") == bs + "begin x"
    assert extract_json('{"s": "' + bs + "begin{aligned}" + '"}')["s"] == bs + "begin{aligned}"


def test_fix_latex_escapes_never_touches_code_or_plain_prose() -> None:
    import json

    from app.llm.reasoning import fix_latex_escapes as fx

    code = "import math\nu = 3.0\ni = 0\ne = 2\nresult = {'u': u, 'i': i, 'e': e}"
    args = fx(json.loads(json.dumps({"code": code, "key_code": code, "answer_md": "where\nu is speed"})))
    assert args["code"] == code and args["key_code"] == code  # still valid Python
    compile(args["code"], "<code>", "exec")
    assert args["answer_md"] == "where\nu is speed"  # no math in it: a real line break
    assert fx("$x\nu = 1$") == "$x" + chr(92) + "nu = 1$"  # inside math it is \nu again
    assert fx("2\times") == "2" + chr(92) + "times"  # tab rule still on in text


def test_extract_json_single_backslash_latex() -> None:
    bs = chr(92)
    latex = bs + "Delta H = 5 " + bs + "mu " + bs + "cdot x^" + bs + "circ"
    assert extract_json('{"s": "' + latex + '"}') == {"s": latex}
    assert extract_json('```json\n{"s": "' + latex + '"}\n```') == {"s": latex}


def test_extract_json_double_backslash_and_real_escapes_unchanged() -> None:
    bs = chr(92)
    assert extract_json('{"s": "' + bs * 2 + "Delta H" + '"}') == {"s": bs + "Delta H"}
    assert extract_json('{"s": "a' + bs + "nb " + bs + '"q' + bs + '" ' + bs + "u00e9" + '"}') == {
        "s": 'a\nb "q" é'
    }


def test_extract_json_single_backslash_leaves_code_alone() -> None:
    bs = chr(92)
    code = "x = 1" + bs + "ny = 2"  # JSON text: a real line break
    out = extract_json('{"code": "' + code + '", "s": "' + bs + 'Delta"}')
    assert out == {"code": "x = 1\ny = 2", "s": bs + "Delta"}
