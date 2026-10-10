"""Switch check: is the active model registry wired up, and does each role answer?

Runs the app's own client code (api/app/llm), so whatever passes here is what the agent
loop will see. Usage, from the repo root of a checkout that has api/ (p1-tracker or main):

    python p1/standin/check.py                       # active registry, config only
    python p1/standin/check.py --live                # + one small call per role
    STUDYFORGE_MODELS_PATH=p1/standin/models.nvidia.yaml python p1/standin/check.py --live

The active registry is the one the app would load: STUDYFORGE_MODELS_PATH if set,
else config/models.yaml (Nebius Token Factory). The key's value is never printed.
--live writes p1/standin/results/<provider>-<UTC time>.json, stamped stand_in true or false.
Exit code 0 only if every check passed.
"""

import argparse
import asyncio
import base64
import io
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from app.llm.client import LLMClient
from app.llm.cost import InMemoryCostRecorder
from app.llm.errors import LLMError
from app.llm.registry import REQUIRED_ROLES, Registry, load_registry
from pydantic import BaseModel

TOKEN_FACTORY_HOST = "api.tokenfactory.nebius.com"
TOOL = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Run Python in the browser sandbox.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
}


class Kind(BaseModel):
    kind: str


def registry_path() -> Path:
    return Path(
        os.environ.get("STUDYFORGE_MODELS_PATH") or ROOT / "config" / "models.yaml"
    )


def is_token_factory(reg: Registry) -> bool:
    return urlparse(reg.base_url).hostname == TOKEN_FACTORY_HOST


def config_checks(reg: Registry) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    rows.append(
        (
            f"key in ${reg.api_key_env}",
            bool(os.environ.get(reg.api_key_env)),
            "set"
            if os.environ.get(reg.api_key_env)
            else "missing: add it in the environment settings",
        )
    )
    for role in REQUIRED_ROLES:
        try:
            ids = [m.id for m in reg.chain(role)]
            rows.append((f"role {role}", True, " -> ".join(ids)))
        except LLMError as err:
            rows.append((f"role {role}", False, str(err)))
    return rows


def tiny_png() -> str:
    """A small white image with typed text: no personal data (AGENTS.md rule 13)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (480, 120), "white")
    ImageDraw.Draw(img).text(
        (10, 50), "A 2 kg mass accelerates at 3 m/s^2. Find F.", fill="black"
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def live_checks(reg: Registry) -> list[dict[str, Any]]:
    recorder = InMemoryCostRecorder()
    client = LLMClient(reg, recorder=recorder)
    user = [{"role": "user", "content": "Reply with the word OK."}]
    calc = [
        {
            "role": "user",
            "content": "A 2 kg mass accelerates at 3 m/s^2. Compute the net force with run_python.",
        }
    ]
    ask_kind = [
        {"role": "user", "content": 'Classify "What is entropy?" as calc or concept.'}
    ]

    async def one(name: str, call: Any, ok: Any) -> dict[str, Any]:
        start = time.monotonic()
        try:
            out = await call
            passed, detail = ok(out)
        except Exception as err:  # noqa: BLE001  (a check reports every failure)
            passed, detail = False, f"{type(err).__name__}: {err}"[:300]
        return {
            "check": name,
            "ok": passed,
            "detail": detail,
            "seconds": round(time.monotonic() - start, 2),
        }

    rows = [
        await one(
            "router text",
            client.chat("router", user),
            lambda r: ("ok" in r.text.lower(), r.text[:80]),
        ),
        await one(
            "solver tool call",
            client.chat_tools("solver", calc, [TOOL]),
            lambda r: (
                bool(r.tool_calls) or "```" in r.text,
                f"tool_calls={[c.name for c in r.tool_calls]}"
                if r.tool_calls
                else "fenced-code fallback"
                if "```" in r.text
                else r.text[:80],
            ),
        ),
        await one(
            "router JSON",
            client.chat_json("router", ask_kind, Kind),
            lambda r: (r[0].kind in ("calc", "concept"), r[0].kind),
        ),
        await one(
            "cross_check text",
            client.chat("cross_check", user),
            lambda r: ("ok" in r.text.lower(), r.text[:80]),
        ),
        await one(
            "vision read",
            client.vision(tiny_png(), "Transcribe the text in this image exactly."),
            lambda r: ("2 kg" in r.text or "2kg" in r.text, r.text[:80]),
        ),
    ]
    rows.append(
        {
            "check": "cost log",
            "ok": len(recorder.records) >= len(rows),
            "detail": f"{len(recorder.records)} call rows, models {sorted({r.model_id for r in recorder.records})}",
            "seconds": 0,
        }
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true", help="make one small call per role")
    args = ap.parse_args(argv)

    path = registry_path()
    reg = load_registry(path)
    nebius = is_token_factory(reg)
    banner = (
        "NEBIUS TOKEN FACTORY (results count)"
        if nebius
        else "STAND-IN (rehearsal only; results do NOT count)"
    )
    print(f"registry : {path}")
    print(f"provider : {reg.base_url}  -> {banner}")

    rows = config_checks(reg)
    for name, ok, detail in rows:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    passed = all(ok for _, ok, _ in rows)

    if args.live:
        if not passed:
            print("live calls skipped: fix the failures above first")
            return 1
        live = asyncio.run(live_checks(reg))
        for r in live:
            print(
                f"[{'PASS' if r['ok'] else 'FAIL'}] {r['check']} ({r['seconds']} s): {r['detail']}"
            )
        passed = all(r["ok"] for r in live)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        host = urlparse(reg.base_url).hostname or "unknown"
        out = Path(__file__).with_name("results") / f"{host}-{stamp}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "stand_in": not nebius,
                    "base_url": reg.base_url,
                    "registry": str(
                        path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
                    ),
                    "passed": passed,
                    "checks": live,
                },
                indent=2,
            )
        )
        print(f"wrote {out.relative_to(ROOT)}")
    print("RESULT:", "ALL PASS" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
