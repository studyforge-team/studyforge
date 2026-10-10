"""Print P1 progress from TRACKER.md, weighted by planned hours."""

from pathlib import Path

rows = []
for line in (
    (Path(__file__).parent / "TRACKER.md").read_text(encoding="utf-8").splitlines()
):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) == 6 and cells[2] in ("MUST", "SHOULD"):
        rows.append((cells[0], cells[2], float(cells[3]), float(cells[4])))

for kind in ("MUST", "SHOULD"):
    items = [r for r in rows if r[1] == kind]
    total = sum(h for _, _, h, _ in items)
    done = sum(h * pct / 100 for _, _, h, pct in items)
    merged = sum(1 for *_, pct in items if pct == 100)
    print(
        f"{kind}: {done / total * 100:.1f}% ({done:.1f} of {total:g} h; {merged}/{len(items)} items merged)"
    )

for tid, kind, h, pct in rows:
    if 0 < pct < 100:
        print(f"  in progress: {tid} {pct:g}%")
