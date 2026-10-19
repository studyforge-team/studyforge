"""Nebius day: one command runs the whole Token Factory integration pass.

    export TF_API_KEY=...           # host env only; never printed or written
    python scripts/nebius_day.py [--super ID --nano ID --vision ID --photo q.jpg]
    python scripts/nebius_day.py --dry-run              # print the plan, no network
    python scripts/nebius_day.py --only quizzes,ch3     # or --skip smoke
    python scripts/nebius_day.py --ch3-labels labels.json --photos DIR

Run from api/. Stages, in order (each PASS / FAIL / SKIP with a one-line result):
  g10      model probe (scripts/g10_probe.py)
  a3_live  tests/unit/llm/test_live_smoke.py with TF_LIVE=1
  smoke    S2/S2b solve suite; api/tests/golden/ if it has problems, else the
           proposals in docs/golden-proposals (NOT official goldens); needs docker
  quizzes  Q1: 10 generated quizzes, target 10/10 valid (numerical keys run in the
           docker runner; without docker only the schema is checked)
  ch3      template picks vs --ch3-labels FILE ([{question, template|null}]), target >= 9/10
  c2       photo reads vs --photos DIR (images + expected.json {file: [keywords]}),
           target >= 7/8
Writes DIR/nebius_day.json (default scripts/out/). Exit 0 if nothing FAILed, 1 if a
stage FAILed, 2 if TF_API_KEY is not set. Model-written code only ever runs in the
docker runner (rule 1).
"""

import argparse
import asyncio
import json
import mimetypes
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from app.agent.chemlab_pick import load_template_specs, pick_template
from app.agent.loop import Deps
from app.agent.quiz import NumericalItem, check_key
from app.agent.quiz_gen import QuizGenerationFailed, generate_quiz
from app.agent.read_question import read_question
from app.agent.smoke import (
    NodeRunner,
    RunnerUnavailable,
    load_problems,
    run_suite,
)
from app.agent.state import InMemoryStore
from app.llm import LLMClient, LLMError, load_registry

STAGES = ["g10", "a3_live", "smoke", "quizzes", "ch3", "c2"]
OFFICIAL = API / "tests" / "golden"
PROPOSALS = API.parent / "docs" / "golden-proposals" / "p1_problems.json"
QUIZ_TOPICS = [
    "first-order reactor design", "ideal gas law", "heat exchanger LMTD",
    "Bernoulli equation", "mass balance on a mixer", "Reynolds number",
    "pipe pressure drop", "Fourier conduction", "chemical equilibrium",
    "distillation McCabe-Thiele",
]  # fmt: skip
Outcome = tuple[str, str, dict[str, Any]]  # status, one-line result, numbers


def _skip(reason: str) -> Outcome:
    return "SKIP", reason, {}


def _scored(name: str, ok: int, total: int, target: int) -> Outcome:
    status = "PASS" if ok >= target else "FAIL"
    return status, f"{ok}/{total} {name} (target {target})", {"ok": ok, "total": total}


def _run(
    cmd: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=API, capture_output=True, text=True, timeout=1800,
        check=False,
        env={**os.environ, **(env or {})},
    )  # fmt: skip


def _tail(proc: subprocess.CompletedProcess[str]) -> str:
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    return lines[-1] if lines else f"exit {proc.returncode}"


def stage_g10(a: argparse.Namespace) -> Outcome:
    cmd = [sys.executable, "scripts/g10_probe.py", "--out", str(a.out)]
    for flag in ("super", "nano", "vision", "photo"):
        if getattr(a, flag):
            cmd += [f"--{flag}", str(getattr(a, flag))]
    proc = _run(cmd)
    return ("PASS" if proc.returncode == 0 else "FAIL"), _tail(proc), {}


def stage_a3_live(a: argparse.Namespace) -> Outcome:
    proc = _run(
        [sys.executable, "-m", "pytest", "tests/unit/llm/test_live_smoke.py", "-q"],
        {"TF_LIVE": "1"},
    )
    tail = _tail(proc)
    if proc.returncode != 0:
        return "FAIL", tail, {}
    if "passed" not in tail or "skipped" in tail:
        return _skip(f"live test skipped: {tail}")
    return "PASS", tail, {}


def _problems_file() -> tuple[Path, str]:
    official = sorted(OFFICIAL.glob("*.json"))
    if official:
        return official[0], "official goldens"
    return PROPOSALS, "proposals, not official goldens"


def stage_smoke(a: argparse.Namespace) -> Outcome:
    path, label = _problems_file()
    llm = LLMClient(load_registry())

    def deps() -> Deps:
        return Deps(llm=llm, store=InMemoryStore(), clock=time.monotonic)

    try:
        report = asyncio.run(run_suite(load_problems(path), deps, NodeRunner()))
    except RunnerUnavailable as err:
        return _skip(f"docker/runner unavailable: {err}"[:120])
    ok = report.passed(0.8, max_median_s=60)
    (a.out / "smoke_report.md").write_text(report.to_markdown(), encoding="utf-8")
    nums = {
        "correct": report.correct,
        "total": report.total,
        "median_s": report.median_seconds,
    }
    line = f"{report.correct}/{report.total} correct, median {report.median_seconds:.1f}s ({label})"
    return ("PASS" if ok else "FAIL"), line, nums


async def _quiz_valid(llm: LLMClient, topic: str, runner: NodeRunner | None) -> bool:
    quiz = await generate_quiz(llm, topic, 5)
    if len(quiz.items) < 3:
        return False
    for item in quiz.items:
        if isinstance(item, NumericalItem) and runner is not None:
            res = await runner.run(item.key_code, 30)
            if res.error or not check_key(res.result, item).ok:
                return False
    return True


def stage_quizzes(a: argparse.Namespace) -> Outcome:
    llm = LLMClient(load_registry())
    runner: NodeRunner | None = NodeRunner()

    async def one(topic: str) -> bool:
        nonlocal runner
        try:
            return await _quiz_valid(llm, topic, runner)
        except RunnerUnavailable:
            runner = None  # schema-only from here on
            return await _quiz_valid(llm, topic, None)
        except (LLMError, QuizGenerationFailed, ValueError):  # invalid quiz
            return False

    async def all_topics() -> int:
        return sum([await one(t) for t in QUIZ_TOPICS])

    ok = asyncio.run(all_topics())
    status, line, nums = _scored(
        "quizzes valid", ok, len(QUIZ_TOPICS), len(QUIZ_TOPICS)
    )
    if runner is None:
        if ok == len(QUIZ_TOPICS):
            return _skip(
                f"{ok}/{len(QUIZ_TOPICS)} schema-valid; keys NOT run (no docker)"
            )
        return "FAIL", line + "; keys NOT run (no docker)", nums
    return status, line, nums


def stage_ch3(a: argparse.Namespace) -> Outcome:
    if not a.ch3_labels:
        return _skip("needs P4 labels")
    labels = json.loads(Path(a.ch3_labels).read_text(encoding="utf-8"))
    llm, specs = LLMClient(load_registry()), load_template_specs()

    async def score() -> int:
        hits = 0
        for lab in labels:
            try:
                run, _ = await pick_template(llm, lab["question"], specs)
                hits += (run.template if run else None) == lab.get("template")
            except (LLMError, ValueError):
                pass  # a failed pick is a miss
        return hits

    return _scored("template picks", asyncio.run(score()), len(labels), 9)


def stage_c2(a: argparse.Namespace) -> Outcome:
    if not a.photos:
        return _skip("needs photos")
    expected: dict[str, list[str]] = json.loads(
        (a.photos / "expected.json").read_text("utf-8")
    )
    llm = LLMClient(load_registry())

    async def score() -> int:
        hits = 0
        for name, words in expected.items():
            mime = mimetypes.guess_type(name)[0] or "image/jpeg"
            try:
                q = await read_question(llm, (a.photos / name).read_bytes(), mime)
                text = f"{q.text} {q.latex}".lower()
                hits += all(w.lower() in text for w in words)
            except (LLMError, ValueError, OSError):
                pass  # an unreadable photo is a miss
        return hits

    return _scored("photo reads", asyncio.run(score()), len(expected), 7)


RUNNERS: dict[str, Callable[[argparse.Namespace], Outcome]] = {
    "g10": stage_g10, "a3_live": stage_a3_live, "smoke": stage_smoke,
    "quizzes": stage_quizzes, "ch3": stage_ch3, "c2": stage_c2,
}  # fmt: skip


def _selected(only: str | None, skip: str | None) -> list[str]:
    names = [s.strip() for s in (only or ",".join(STAGES)).split(",") if s.strip()]
    drop = {s.strip() for s in (skip or "").split(",")}
    unknown = [n for n in [*names, *drop - {""}] if n not in STAGES]
    if unknown:
        raise SystemExit(
            f"unknown stage(s): {', '.join(unknown)}; known: {', '.join(STAGES)}"
        )
    return [s for s in STAGES if s in names and s not in drop]


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Nebius day: whole integration pass")
    ap.add_argument("--only")
    ap.add_argument("--skip")
    ap.add_argument("--out", type=Path, default=API / "scripts" / "out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--super")
    ap.add_argument("--nano")
    ap.add_argument("--vision")
    ap.add_argument("--photo", type=Path)
    ap.add_argument("--ch3-labels", type=Path)
    ap.add_argument("--photos", type=Path)
    a = ap.parse_args(argv)
    names = _selected(a.only, a.skip)
    if a.dry_run:
        print("Nebius day plan (no network calls):")
        for n in names:
            print(f"  {n}: {stage_doc(n)}")
        return 0

    secret = os.environ.get("TF_API_KEY", "")
    a.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for n in names:
        t0 = time.monotonic()
        if not secret:
            status, line, nums = _skip("TF_API_KEY not set")
        else:
            try:
                status, line, nums = RUNNERS[n](a)
            except Exception as exc:  # noqa: BLE001  a broken stage must not stop the rest
                status, line, nums = "FAIL", f"{type(exc).__name__}: {exc}", {}
        rows.append({
            "stage": n, "status": status, "result": _scrub(line, secret)[:300],
            "numbers": nums, "seconds": round(time.monotonic() - t0, 2),
        })  # fmt: skip
    (a.out / "nebius_day.json").write_text(
        json.dumps({"stages": rows}, indent=2), "utf-8"
    )
    print(f"{'stage':<9}{'status':<7}{'secs':>7}  result")
    for r in rows:
        print(f"{r['stage']:<9}{r['status']:<7}{r['seconds']:>7}  {r['result']}")
    if not secret:
        return 2
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


def stage_doc(name: str) -> str:
    return {
        "g10": "model probe", "a3_live": "live LLM client test",
        "smoke": "S2/S2b solve suite (docker)", "quizzes": "Q1: 10 quizzes valid",
        "ch3": "template picks (needs --ch3-labels)", "c2": "photo reads (needs --photos)",
    }[name]  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
