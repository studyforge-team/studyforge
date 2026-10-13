"""Write every template's SPEC to api/app/agent/chemlab_specs.json for CH3.

    python chemlab/tools/export_specs.py

The api never imports chemlab at run time; it reads this file instead (the agent loop's
`Deps.templates`). An api test fails when the file and the templates disagree.
"""

import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "api" / "app" / "agent" / "chemlab_specs.json"


def specs() -> dict[str, dict[str, dict]]:
    names = sorted(
        p.stem
        for p in (ROOT / "chemlab" / "templates").glob("*.py")
        if p.stem[0] != "_"
    )
    out = {}
    for name in names:
        mod = importlib.import_module(f"chemlab.{name}")
        # a stale non-editable chemlab install would export the wrong SPECs
        src = Path(mod.__file__ or "").resolve()
        assert src.parent == (ROOT / "chemlab" / "templates").resolve(), src
        out[mod.TEMPLATE] = {k: dict(v) for k, v in mod.SPEC.items()}
    return out


def render() -> str:
    return json.dumps(specs(), indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
