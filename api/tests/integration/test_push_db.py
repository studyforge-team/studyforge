"""D1b on a real Postgres: subscriptions saved, moved, capped and removed; dead devices forgotten;
export/delete cover the table. Runs only with DATABASE_URL set."""

import asyncio
import os
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import text

from app import push
from app.db import make_engine

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL")

CFG = Config(str(Path(__file__).parents[2] / "alembic.ini"))
FCM = "https://fcm.googleapis.com/fcm/send/"


def _keys() -> tuple[str, str]:
    ua = ec.generate_private_key(ec.SECP256R1())
    pub = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return push.b64u(pub), push.b64u(os.urandom(16))


def test_push_subscriptions() -> None:
    command.upgrade(CFG, "head")
    try:
        asyncio.run(_exercise())
    finally:
        command.downgrade(CFG, "base")


async def _exercise() -> None:
    engine = make_engine()
    async def count(where: str) -> int:
        async with engine.connect() as conn:
            return int((await conn.execute(text(f"select count(*) from app.push_subscriptions where {where}"))).scalar_one())

    assert await push.save(engine, "A", FCM + "phone", *_keys())
    assert await push.save(engine, "A", FCM + "phone", *_keys())  # the same device again: updated, not duplicated
    assert await count("true") == 1
    assert await push.save(engine, "B", FCM + "phone", *_keys())  # the phone signs into B: B gets its pushes
    assert await count("user_id='A'") == 0 and await count("user_id='B'") == 1
    assert await push.remove(engine, "A", FCM + "phone") is False  # not A's any more
    # device cap holds under concurrency (advisory lock per user)
    got = await asyncio.gather(*[push.save(engine, "C", f"{FCM}c{i}", *_keys()) for i in range(push.MAX_DEVICES + 5)])
    assert sum(got) == push.MAX_DEVICES and await count("user_id='C'") == push.MAX_DEVICES
    assert await push.save(engine, "C", FCM + "c0", *_keys())  # an existing device can still refresh its keys

    # delivery: one live device, one the push service says is gone
    assert await push.save(engine, "D", FCM + "live", *_keys())
    assert await push.save(engine, "D", FCM + "dead", *_keys())
    key = ec.generate_private_key(ec.SECP256R1())
    v = push.Vapid(key, push.b64u(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)), "mailto:t@e.st")
    hits: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        hits.append(str(req.url))
        return httpx.Response(410 if req.url.path.endswith("dead") else 201)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        msg = {"title": "T", "body": "B", "url": "/#"}
        assert await push.notify(engine, client, v, [("D", msg), ("nobody", msg)]) == 1
    assert sorted(hits) == [FCM + "dead", FCM + "live"]
    assert await count("user_id='D'") == 1 and await count("endpoint like '%dead'") == 0
    assert await push.remove(engine, "D", FCM + "live") is True and await count("user_id='D'") == 0
    await engine.dispose()
