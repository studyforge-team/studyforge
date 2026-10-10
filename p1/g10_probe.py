"""G10 model probe: list Token Factory models, then one call per check.

Usage (needs TF_API_KEY and network access to api.tokenfactory.nebius.com):
    python p1/g10_probe.py                      # list models only
    python p1/g10_probe.py --super ID --nano ID --vision ID --photo q.jpg

Stand-in rehearsal (same checks, another OpenAI-compatible provider):
    python p1/g10_probe.py --base-url URL --key-env NAME --super ID ...
The output file then carries "stand_in": true; only Token Factory results count.

Writes p1/g10_results.json: per call the model ID, tokens, latency, finish_reason
and how reasoning text arrived. Prices are not in /v1/models: copy them from the
Token Factory pricing page into config/models.yaml. Every call is capped at
max_tokens so the whole probe costs cents.
"""

import argparse
import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

from openai import APIError, OpenAI

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
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
CALC = "A 2 kg mass accelerates at 3 m/s^2. What net force acts on it?"


def think(on: bool) -> dict[str, Any]:
    return {"chat_template_kwargs": {"enable_thinking": on}}


def probe(client: OpenAI, name: str, **kw: Any) -> dict[str, Any]:
    start = time.monotonic()
    row: dict[str, Any] = {"check": name, "model": kw["model"]}
    try:
        resp = client.chat.completions.create(
            max_tokens=kw.pop("max_tokens", 400), **kw
        )
    except APIError as exc:  # record every API failure; this is a probe
        row.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
        return row
    msg = resp.choices[0].message
    content = msg.content or ""
    extra = msg.model_extra or {}
    row.update(
        ok=True,
        latency_s=round(time.monotonic() - start, 2),
        prompt_tokens=resp.usage.prompt_tokens if resp.usage else None,
        completion_tokens=resp.usage.completion_tokens if resp.usage else None,
        finish_reason=resp.choices[0].finish_reason,
        reasoning_field=next(
            (k for k in ("reasoning_content", "reasoning") if extra.get(k)), None
        ),
        think_open_tag="<think>" in content,
        think_close_tag="</think>" in content,
        tool_calls=[
            c.function.name for c in msg.tool_calls or [] if c.type == "function"
        ],
        content=content[:300],
    )
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--super")
    ap.add_argument("--nano")
    ap.add_argument("--vision")
    ap.add_argument("--photo", type=Path, help="question photo with no personal data")
    ap.add_argument("--base-url", default=BASE_URL, help="default: Token Factory")
    ap.add_argument("--key-env", default="TF_API_KEY", help="env var holding the key")
    args = ap.parse_args()
    stand_in = args.base_url.rstrip("/") != BASE_URL.rstrip("/")

    client = OpenAI(
        base_url=args.base_url,
        api_key=os.environ[args.key_env],
        max_retries=0,
        timeout=120,
    )
    ids = sorted(m.id for m in client.models.list())
    print("\n".join(ids))
    rows: list[dict[str, Any]] = []
    user = [{"role": "user", "content": CALC}]

    if args.super:
        m = args.super
        rows.append(
            probe(client, "super_text", model=m, messages=user, extra_body=think(False))
        )
        rows.append(
            probe(
                client,
                "super_reasoning_on",
                model=m,
                messages=user,
                extra_body=think(True),
                max_tokens=2000,
            )
        )
        rows.append(
            probe(
                client,
                "super_reasoning_off",
                model=m,
                messages=user,
                extra_body=think(False),
            )
        )
        rows.append(
            probe(
                client,
                "super_tool_call",
                model=m,
                messages=user,
                tools=[TOOL],
                tool_choice="auto",
                extra_body=think(True),
                max_tokens=2000,
            )
        )
    if args.nano:
        ask = [
            {
                "role": "user",
                "content": 'Classify: "'
                + CALC
                + '". Reply with only JSON {"kind": "calc" or "concept"}.',
            }
        ]
        rows.append(
            probe(
                client,
                "nano_json_prompt_only",
                model=args.nano,
                messages=ask,
                extra_body=think(False),
            )
        )
        rows.append(
            probe(
                client,
                "nano_json_mode",
                model=args.nano,
                messages=ask,
                response_format={"type": "json_object"},
                extra_body=think(False),
            )
        )
    if args.vision and args.photo:
        mime = mimetypes.guess_type(args.photo.name)[0] or "image/jpeg"
        url = (
            f"data:{mime};base64," + base64.b64encode(args.photo.read_bytes()).decode()
        )
        parts = [
            {
                "type": "text",
                "text": "Transcribe the question in this image exactly. Use LaTeX for maths.",
            },
            {"type": "image_url", "image_url": {"url": url}},
        ]
        rows.append(
            probe(
                client,
                "vision_photo",
                model=args.vision,
                messages=[{"role": "user", "content": parts}],
                max_tokens=800,
            )
        )

    name = "g10_results_standin.json" if stand_in else "g10_results.json"
    out = Path(__file__).with_name(name)
    meta = {"base_url": args.base_url, "stand_in": stand_in}
    out.write_text(json.dumps({**meta, "models": ids, "calls": rows}, indent=2))
    for r in rows:
        print(
            r["check"],
            "OK" if r["ok"] else "FAIL",
            r.get("latency_s", ""),
            r.get("error", ""),
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
