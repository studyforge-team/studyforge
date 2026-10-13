"""NR done-when: notes search returns the right slide for 8/10 questions; real Postgres.

The slides and questions below are synthetic TEST FIXTURES for code correctness (written for this
test, phrased differently from each other). They are not labelled evaluation data.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app import notes
from app.db import make_engine
from app.routers import checkins, me, solve, uploads
from app.routers import notes as notes_router
from tests.unit.conftest import MemoryStorage

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")
CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))

SLIDES = [
    "Log mean temperature difference LMTD for a heat exchanger: Q equals U A times LMTD, counter-current flow gives a larger driving force than co-current flow.",
    "McCabe-Thiele method: step off equilibrium stages between the operating lines on the x-y diagram to find the number of trays in a distillation column.",
    "CSTR design: conversion X equals tau k over one plus tau k for a first order reaction in a continuous stirred tank, volume V from the design equation.",
    "Flash vaporization with Raoult's law: partial pressure equals mole fraction times saturation vapour pressure, Rachford-Rice solves the vapour fraction.",
    "Pipe flow pressure drop: Darcy friction factor f, head loss equals f L over D times velocity squared over two g, Moody chart for turbulent flow.",
    "Steady conduction through a wall: Fourier's law, heat flux equals minus thermal conductivity times temperature gradient, series thermal resistances.",
    "Arrhenius equation: rate constant k equals A exp of minus activation energy over R T, plot ln k against one over T to get the slope.",
    "Reynolds number: density times velocity times diameter over viscosity, laminar below 2100, turbulent above 4000, transition in between.",
    "NPSH available and required for a centrifugal pump: cavitation occurs when suction pressure falls to the vapour pressure of the liquid.",
    "Recycle and purge: a purge stream removes inerts from the loop so they do not accumulate, overall conversion exceeds single pass conversion.",
]
QUESTIONS = [  # question i should hit SLIDES[i] (page i+1) first
    "how do I find heat duty from the log mean temperature difference",
    "number of trays in a distillation column using the equilibrium curve",
    "what conversion do I get from a stirred tank reactor with first order kinetics",
    "vapour fraction of a flash drum using Raoult",
    "pressure drop in a pipe from the friction factor",
    "heat flux through a wall with thermal conductivity",
    "effect of temperature on the rate constant and activation energy",
    "is the flow laminar or turbulent, how do I compute it from viscosity",
    "why does my pump cavitate near the suction",
    "why do we bleed off inerts in a recycle loop",
]


def make_pdf(pages: list[str]) -> bytes:
    """Minimal hand-written PDF, one wrapped Helvetica text block per page (no parens/backslashes)."""
    objs = [b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Kids[" + b" ".join(b"%d 0 R" % (4 + 2 * i) for i in range(len(pages)))
            + b"]/Count %d>>" % len(pages),
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    for i, t in enumerate(pages):
        lines, cur = [], ""
        for w in t.split():
            if len(cur) + len(w) > 70:
                lines.append(cur)
                cur = ""
            cur += w + " "
        lines.append(cur)
        stream = b"BT /F1 10 Tf 12 780 Td 12 TL " + b" T* ".join(b"(%s) Tj" % ln.encode() for ln in lines) + b" ET"
        objs.append(b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 3 0 R>>>>"
                    b"/Contents %d 0 R>>" % (5 + 2 * i))
        objs.append(b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream")
    out, offs = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)


def test_make_pdf_roundtrip() -> None:
    got = notes.pdf_pages(make_pdf(SLIDES))
    assert [p for p, _ in got] == list(range(1, 11)) and "Fourier" in got[5][1]


async def _exercise() -> None:
    engine = make_engine()

    async def n(sql: str) -> int:
        async with engine.connect() as c:
            return int((await c.execute(text(sql))).scalar_one())

    mem = MemoryStorage()
    nid, nid_b, qid, png = "notes-" + "a" * 32, "notes-" + "b" * 32, "question-" + "c" * 32, "notes-" + "d" * 32
    await mem.put(f"A/{nid}", make_pdf(SLIDES), "application/pdf")
    await mem.put(f"B/{nid_b}", make_pdf(["Secret quantum chromodynamics lecture of user B only."]), "application/pdf")
    await mem.put(f"A/{qid}", b"\x89PNG\r\n\x1a\n", "image/png")
    await mem.put(f"A/{png}", b"\x89PNG\r\n\x1a\n", "image/png")
    who = {"u": "A"}
    sent: list[str] = []

    async def http() -> AsyncIterator[httpx.AsyncClient]:
        def ok(req: httpx.Request) -> httpx.Response:
            sent.append(str(req.url))
            return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(ok)) as c:
            yield c

    app = FastAPI()
    app.include_router(notes_router.router)
    app.include_router(me.router)
    app.dependency_overrides |= {
        solve.current_user: lambda: who["u"], me.current_user: lambda: who["u"],
        checkins.get_engine: lambda: engine, me.get_engine: lambda: engine, me.get_http: http,
        uploads.get_storage: lambda: mem, uploads.get_storage_opt: lambda: mem}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        async def idx(up: str) -> httpx.Response:
            return await c.post(f"/api/v1/notes/{up}/index")

        async def hits(q: str) -> list[dict[str, object]]:
            r = await c.get("/api/v1/notes/search", params={"q": q})
            assert r.status_code == 200
            return r.json()["hits"]  # type: ignore[no-any-return]

        assert (await idx(nid)).json() == {"pages": 10}
        assert (await idx(nid)).json() == {"pages": 10}  # re-index replaces, no duplicates
        assert await n("select count(*) from app.note_chunks where user_id='A'") == 10
        assert (await idx(qid)).status_code == 422
        assert (await idx(nid_b)).status_code == 404  # B's upload id, asked as A
        assert (await idx(png)).status_code == 415  # a notes id that is not a PDF
        assert (await c.get("/api/v1/notes/search", params={"q": ""})).status_code == 422

        who["u"] = "B"
        assert (await idx(nid_b)).json() == {"pages": 1}
        assert await hits("heat exchanger LMTD") == []  # A's slides are invisible to B
        assert (await hits("quantum chromodynamics"))[0]["page"] == 1
        who["u"] = "A"
        assert await hits("quantum chromodynamics") == []
        assert await hits("the of and") == []  # stopwords only

        right = 0
        for i, q in enumerate(QUESTIONS):
            h = await hits(q)
            right += bool(h) and h[0]["page"] == i + 1 and h[0]["upload_id"] == nid
        print(f"NRSCORE {right}/10")
        assert right >= 8

        exp = (await c.get("/api/v1/me/export")).json()
        assert len(exp["note_chunks"]) == 10 and {r["user_id"] for r in exp["note_chunks"]} == {"A"}
        assert all("tsv" not in r for r in exp["note_chunks"])  # generated column is derived noise
        assert (await c.delete("/api/v1/me")).status_code == 204
        assert await n("select count(*) from app.note_chunks where user_id='A'") == 0
        assert await n("select count(*) from app.note_chunks where user_id='B'") == 1
    await engine.dispose()


def test_notes_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    assert ScriptDirectory.from_config(CFG).get_heads() == ["0007"]
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")
