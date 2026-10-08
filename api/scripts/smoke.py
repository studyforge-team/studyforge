"""Run the smoke/eval suite for real: python scripts/smoke.py PROBLEMS.json [--limit N].

Needs Token Factory access (key in the host env) and docker for the sandbox runner.
Exits 1 if the threshold is missed, 2 if the runner is unavailable.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.loop import Deps
from app.agent.smoke import (
    NodeRunner,
    RunnerUnavailable,
    load_problems,
    run_suite,
)
from app.agent.state import InMemoryStore
from app.llm import LLMClient, load_registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="StudyForge smoke/eval harness")
    ap.add_argument("problems", type=Path, help="problems JSON (list or {problems})")
    ap.add_argument("--limit", type=int, default=None, help="only the first N")
    ap.add_argument("--threshold", type=float, default=0.8, help="min share correct")
    ap.add_argument("--max-median-s", type=float, default=None, help="S2: 60")
    ap.add_argument("--out", type=Path, default=None, help="write the markdown report")
    args = ap.parse_args(argv)

    problems = load_problems(args.problems)[: args.limit]
    llm = LLMClient(load_registry())

    def deps_factory() -> Deps:
        return Deps(llm=llm, store=InMemoryStore(), clock=time.monotonic)

    try:
        report = asyncio.run(run_suite(problems, deps_factory, NodeRunner()))
    except RunnerUnavailable as err:
        print(err, file=sys.stderr)
        return 2
    md = report.to_markdown()
    print(md)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    ok = report.passed(args.threshold, max_median_s=args.max_median_s)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
