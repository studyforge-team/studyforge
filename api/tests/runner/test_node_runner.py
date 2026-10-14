"""Real NodeRunner in real docker (`--network none`, no secrets). CI-only: set RUNNER_DOCKER=1
(needs docker, runner/pyodide from runner/setup.mjs, and the node:22-slim image).

The CI job puts SF_CANARY_SECRET in this pytest process's env; nothing may ever echo it."""

import asyncio
import json
import os
from typing import Any

import pytest

from app.agent.smoke import REPO_ROOT, NodeRunner
from app.agent.steps import ResultBody

pytestmark = pytest.mark.skipif(
    os.environ.get("RUNNER_DOCKER") != "1", reason="needs docker: RUNNER_DOCKER=1"
)
ATTACKS: dict[str, str] = json.loads((REPO_ROOT / "runner" / "attacks.json").read_text())
CANARY = os.environ.get("SF_CANARY_SECRET", "no-canary-set")


def run(code: str, timeout_s: float = 60, grace_s: float = 20) -> ResultBody:
    return asyncio.run(NodeRunner(grace_s=grace_s).run(code, timeout_s))


def no_canary(body: ResultBody) -> None:
    assert CANARY not in body.model_dump_json()


def test_canary_is_set_in_ci() -> None:
    assert os.environ.get("CI") != "true" or CANARY != "no-canary-set"


@pytest.mark.parametrize("name", ATTACKS)
def test_attack_fails_safely(name: str) -> None:
    body = run(ATTACKS[name])
    no_canary(body)
    # a runner error is a safe outcome; a reply means the attack code ran and must report failure
    result: Any = body.result
    assert body.error is not None or (result is not None and result["ok"] is False), body


def test_numpy_scipy_print() -> None:
    body = run(
        "import numpy as np\nfrom scipy.optimize import fsolve\nprint('hi')\n"
        "result = {'x': float(fsolve(lambda x: x**2 - 4, 1.0)[0]), 'a': np.arange(3)}"
    )
    assert body.error is None and body.stdout == "hi\n"
    assert body.result is not None and abs(body.result["x"] - 2) < 1e-6
    assert body.result["a"] == [0, 1, 2]


def test_matplotlib_figure_is_base64_png() -> None:
    import base64

    body = run("import matplotlib.pyplot as plt\nplt.plot([1, 2])\nresult = {}")
    assert len(body.figures) == 1
    assert base64.b64decode(body.figures[0])[1:4] == b"PNG"


def test_missing_result_is_error() -> None:
    assert "result" in (run("x = 1").error or "")


def test_cpu_loop_is_killed_by_container_kill() -> None:
    body = run("while True: pass", timeout_s=2, grace_s=10)
    assert body.error == "timeout"


def test_container_starts_with_hardened_flags() -> None:
    body = run("import js\nresult = {'ok': True}")  # smoke: container starts with all flags
    assert body.error is None
