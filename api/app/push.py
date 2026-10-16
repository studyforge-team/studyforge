"""Web push (D1b): a phone notification for each reminder and check-in the keep-alive ping sends.

No push library: the payload is encrypted with aes128gcm as RFC 8291 specifies, and the request
is signed with a VAPID JWT (RFC 8292, ES256), using cryptography, PyJWT and httpx, which are
already pinned. (pywebpush 2.4+ needs cryptography 47, and 2.3 pulls in requests, aiohttp and a
PSF-licensed transitive dependency; see the D1b PR.)

Keys live only in the host env (AGENTS.md rule 4), as printed by `npx web-push generate-vapid-keys`:
VAPID_PUBLIC_KEY (65-byte uncompressed P-256 point, base64url), VAPID_PRIVATE_KEY (32-byte scalar,
base64url), VAPID_SUBJECT ("mailto:..." contact for the push services).
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import push_subscriptions

# The server only ever POSTs to the browsers' own push services: a subscription naming any other
# host is refused, so a user cannot make the API call an address of their choosing.
PUSH_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "push.apple.com", "notify.windows.com")
RECORD_SIZE = 4096
TTL_S = 24 * 3600  # a reminder still matters for a day if the phone is off
MAX_BODY = 3000  # bytes of JSON before encryption; push services accept about 4 KB


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def push_host_ok(endpoint: str) -> bool:
    """Parsed with httpx, the parser that sends: https, no user:password@, default port, a plain
    ASCII host on one of PUSH_HOSTS, and nothing hidden in the URL (spaces, tabs, control characters)."""
    if not endpoint.isascii() or any(c <= " " or c == "\x7f" or c == "\\" for c in endpoint):
        return False
    try:
        u = httpx.URL(endpoint)
    except (httpx.InvalidURL, ValueError, TypeError):
        return False
    host = u.host.lower()
    if u.scheme != "https" or u.userinfo or u.port not in (None, 443) or not re.fullmatch(r"[a-z0-9.-]+", host):
        return False
    return any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def valid_point(p256dh: str) -> bool:
    """A browser's key: an uncompressed P-256 point that is really on the curve."""
    try:
        raw = unb64u(p256dh)
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    except (ValueError, TypeError):  # bad base64 (binascii.Error is a ValueError) or not on the curve
        return False
    return len(raw) == 65 and raw[0] == 4


@dataclass(frozen=True)
class Vapid:
    private_key: ec.EllipticCurvePrivateKey
    public_b64: str
    subject: str


def vapid_from_env() -> Vapid | None:
    """None when push is not switched on (any of the three variables missing or wrong)."""
    pub, priv, sub = (os.environ.get(k, "").strip() for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"))
    if not (pub and priv and sub.startswith(("mailto:", "https://"))):
        return None
    try:
        key = ec.derive_private_key(int.from_bytes(unb64u(priv), "big"), ec.SECP256R1())
    except ValueError:
        return None
    raw_pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    if b64u(raw_pub) != pub.rstrip("="):  # the pair must match, or every push is refused
        return None
    return Vapid(key, b64u(raw_pub), sub)


def vapid_header(endpoint: str, v: Vapid, now: float | None = None) -> str:
    parts = urlsplit(endpoint)
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int((now or time.time()) + 12 * 3600), "sub": v.subject}
    token = jwt.encode(claims, v.private_key, algorithm="ES256")
    return f"vapid t={token}, k={v.public_b64}"


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(plaintext: bytes, p256dh: str, auth: str, *,
            server_key: ec.EllipticCurvePrivateKey | None = None, salt: bytes | None = None) -> bytes:
    """RFC 8291 section 3.4 / RFC 8188: one aes128gcm record. server_key and salt are for tests."""
    ua_public = unb64u(p256dh)
    auth_secret = unb64u(auth)
    as_key = server_key or ec.generate_private_key(ec.SECP256R1())
    as_public = as_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ecdh = as_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public))
    ikm = _hkdf(auth_secret, ecdh, b"WebPush: info\x00" + ua_public + as_public, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    body = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)  # 0x02: last (and only) record
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + body


def message(job: dict[str, Any]) -> dict[str, str]:
    """What the phone shows for a sent job (app/reminders.py rows): title, body, page to open."""
    p = job["payload"]
    if str(p.get("slot", "")).startswith("checkin"):
        return {"title": "StudyForge check-in", "body": f"Did you finish {p['title']}? One quick question.",
                "url": f"{p['prep']}?checkin={job['id']}"}
    when = {"t-3d": "in 3 days", "t-1d": "tomorrow", "morning": "today"}.get(p.get("slot", ""), "soon")
    return {"title": "StudyForge reminder", "body": f"{p['title']} is due {when}. Tap for your prep pack.",
            "url": str(p["prep"])}


def _payload(msg: dict[str, str]) -> bytes:
    data = json.dumps(msg, ensure_ascii=False).encode()
    body = msg["body"]
    while len(data) > MAX_BODY and body:  # a very long task title: shorten the body, keep the link
        body = body[: len(body) - max(1, (len(data) - MAX_BODY) // 6)]  # ≤ 6 bytes per char once escaped
        data = json.dumps(dict(msg, body=body + "…"), ensure_ascii=False).encode()
    return data


async def send(client: httpx.AsyncClient, sub: dict[str, str], msg: dict[str, str], v: Vapid) -> int:
    """POST one notification; returns the push service's status (201 = accepted). Never raises on HTTP."""
    if not push_host_ok(sub["endpoint"]):
        return 0
    try:  # anything wrong with one device (a bad key, a network error) must not stop the others
        headers = {"Authorization": vapid_header(sub["endpoint"], v), "Content-Encoding": "aes128gcm",
                   "Content-Type": "application/octet-stream", "TTL": str(TTL_S), "Urgency": "normal"}
        r = await client.post(sub["endpoint"], content=encrypt(_payload(msg), sub["p256dh"], sub["auth"]), headers=headers)
    except Exception:  # noqa: BLE001 - one device's failure, whatever it is, must not stop the batch
        return 0  # never log the exception: it can carry the endpoint (a per-device capability URL)
    return r.status_code


# ---- storage (app.push_subscriptions) and delivery

MAX_DEVICES = 10  # per user: phones, laptops, a second browser
PARALLEL = 20  # sends at once
DELIVER_S = 15  # whole delivery inside one keep-alive ping
log = logging.getLogger(__name__)


async def save(engine: AsyncEngine, user_id: str, endpoint: str, p256dh: str, auth: str) -> bool:
    """Store or move a subscription to this user (a device signs into another account: the newest
    owner gets its pushes). False when the user already has MAX_DEVICES other devices."""
    async with engine.begin() as conn:
        await conn.execute(text("select pg_advisory_xact_lock(hashtext('push:' || :u))"), {"u": user_id})
        others = (await conn.execute(
            select(func.count()).select_from(push_subscriptions)
            .where(push_subscriptions.c.user_id == user_id, push_subscriptions.c.endpoint != endpoint)
        )).scalar_one()
        if others >= MAX_DEVICES:
            return False
        stmt = insert(push_subscriptions).values(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        await conn.execute(stmt.on_conflict_do_update(
            index_elements=["endpoint"],
            set_={"user_id": stmt.excluded.user_id, "p256dh": stmt.excluded.p256dh, "auth": stmt.excluded.auth},
        ))
    return True


async def remove(engine: AsyncEngine, user_id: str, endpoint: str) -> bool:
    q = push_subscriptions.delete().where(push_subscriptions.c.user_id == user_id, push_subscriptions.c.endpoint == endpoint)
    async with engine.begin() as conn:
        return (await conn.execute(q)).rowcount == 1


async def devices(engine: AsyncEngine, user_ids: list[str]) -> list[dict[str, str]]:
    c = push_subscriptions.c
    async with engine.connect() as conn:
        rows = await conn.execute(select(c.user_id, c.endpoint, c.p256dh, c.auth).where(c.user_id.in_(user_ids)))
        return [dict(r) for r in rows.mappings()]


async def notify(engine: AsyncEngine, client: httpx.AsyncClient, v: Vapid,
                 items: list[tuple[str, dict[str, str]]]) -> int:
    """Send each (user_id, message) to all that user's devices; returns how many the push services
    accepted. A device the service reports gone (404/410) is forgotten."""
    subs = await devices(engine, sorted({u for u, _ in items})) if items else []
    by_user: dict[str, list[dict[str, str]]] = {}
    for s in subs:
        by_user.setdefault(s["user_id"], []).append(s)
    sends = [(s, msg) for u, msg in items for s in by_user.get(u, [])]
    gate = asyncio.Semaphore(PARALLEL)

    async def one(s: dict[str, str], msg: dict[str, str]) -> int:
        async with gate:
            return await send(client, s, msg, v)

    codes = await asyncio.gather(*(one(s, msg) for s, msg in sends))
    if failed := sum(not 200 <= c < 300 for c in codes):
        log.info("push: %d of %d sends not accepted", failed, len(codes))  # counts only, never URLs
    gone = sorted({s["endpoint"] for (s, _), code in zip(sends, codes, strict=True) if code in (404, 410)})
    if gone:
        async with engine.begin() as conn:
            await conn.execute(push_subscriptions.delete().where(push_subscriptions.c.endpoint.in_(gone)))
    return sum(200 <= code < 300 for code in codes)


async def deliver(engine: AsyncEngine, jobs: list[dict[str, Any]]) -> int | None:
    """Called by /keepalive with the jobs drain() just marked sent. None when push is off."""
    v = vapid_from_env()
    if v is None:
        return None
    items = []
    for j in jobs:
        try:
            items.append((j["user_id"], message(j)))
        except (KeyError, TypeError):
            continue  # a malformed job is still in the inbox; it just gets no notification
    if not items:
        return 0
    async with asyncio.timeout(DELIVER_S), httpx.AsyncClient(timeout=10) as client:  # the ping is public: bounded
        return await notify(engine, client, v, items)
