"""scripts/nebius_day.py: orchestration only. No network, no docker."""

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import nebius_day as nd

KEY = "sk-" + "x" * 20


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def make(name: str) -> Any:
        def fake(_a: Any) -> nd.Outcome:
            calls.append(name)
            return "PASS", f"{name} ok {KEY}", {"n": 1}

        return fake

    for n in nd.STAGES:
        monkeypatch.setitem(nd.RUNNERS, n, make(n))
    return calls


def run(tmp_path: Path, *args: str) -> int:
    return nd.main(["--out", str(tmp_path), *args])


def summary(tmp_path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads((tmp_path / "nebius_day.json").read_text())
    return {r["stage"]: r for r in data["stages"]}


def test_dry_run_lists_all_stages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TF_API_KEY", raising=False)
    assert run(tmp_path, "--dry-run") == 0
    out = capsys.readouterr().out
    assert all(n in out for n in nd.STAGES)
    assert not (tmp_path / "nebius_day.json").exists()


def test_missing_key_skips_model_stages_exit_2(
    tmp_path: Path, fakes: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TF_API_KEY", raising=False)
    assert run(tmp_path) == 2
    rows = summary(tmp_path)
    assert fakes == []
    assert all(r["status"] == "SKIP" for r in rows.values())
    assert rows["g10"]["result"] == "TF_API_KEY not set"


def test_only_and_skip_filtering(
    tmp_path: Path, fakes: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TF_API_KEY", KEY)
    assert run(tmp_path, "--only", "quizzes,g10") == 0
    assert fakes == ["g10", "quizzes"]
    fakes.clear()
    assert run(tmp_path, "--skip", "smoke,c2") == 0
    assert fakes == ["g10", "a3_live", "quizzes", "ch3"]
    with pytest.raises(SystemExit):
        run(tmp_path, "--only", "nope")


def test_ch3_and_c2_skip_without_inputs(tmp_path: Path) -> None:
    a = nd.argparse.Namespace(ch3_labels=None, photos=None)
    assert nd.stage_ch3(a)[:2] == ("SKIP", "needs P4 labels")
    assert nd.stage_c2(a)[:2] == ("SKIP", "needs photos")


def test_failing_stage_reported_and_later_stages_run(
    tmp_path: Path, fakes: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TF_API_KEY", KEY)

    def boom(_a: Any) -> nd.Outcome:
        raise RuntimeError("kaput")

    monkeypatch.setitem(nd.RUNNERS, "a3_live", boom)
    assert run(tmp_path) == 1
    rows = summary(tmp_path)
    assert rows["a3_live"]["status"] == "FAIL"
    assert "kaput" in rows["a3_live"]["result"]
    assert rows["quizzes"]["status"] == "PASS"
    assert "quizzes" in fakes


def test_summary_shape_and_key_never_printed(
    tmp_path: Path,
    fakes: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TF_API_KEY", KEY)
    assert run(tmp_path) == 0
    shown = capsys.readouterr()
    text = (tmp_path / "nebius_day.json").read_text()
    assert KEY not in shown.out + shown.err + text
    rows = summary(tmp_path)
    assert list(rows) == nd.STAGES
    assert set(rows["g10"]) == {"stage", "status", "result", "numbers", "seconds"}


def _proc(out: str, code: int = 0) -> Any:
    return nd.subprocess.CompletedProcess([], code, stdout=out, stderr="")


def test_a3_live_skip_is_not_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    a = nd.argparse.Namespace()
    monkeypatch.setattr(nd, "_run", lambda *_a, **_k: _proc("1 skipped in 0.1s"))
    status, line, _ = nd.stage_a3_live(a)
    assert status == "SKIP"
    assert line.startswith("live test skipped:")
    monkeypatch.setattr(nd, "_run", lambda *_a, **_k: _proc("1 passed in 0.1s"))
    assert nd.stage_a3_live(a)[0] == "PASS"
    monkeypatch.setattr(nd, "_run", lambda *_a, **_k: _proc("1 failed", 1))
    assert nd.stage_a3_live(a)[0] == "FAIL"


def test_quizzes_without_docker_is_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(_llm: Any, _topic: str, runner: Any) -> bool:
        if runner is not None:
            raise nd.RunnerUnavailable("no docker")
        return True

    monkeypatch.setattr(nd, "LLMClient", lambda *_a, **_k: object())
    monkeypatch.setattr(nd, "load_registry", lambda: None)
    monkeypatch.setattr(nd, "_quiz_valid", fake)
    status, line, _ = nd.stage_quizzes(nd.argparse.Namespace())
    assert status == "SKIP"
    assert line == "10/10 schema-valid; keys NOT run (no docker)"
