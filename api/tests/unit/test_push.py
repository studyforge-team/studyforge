import json
import os
from collections.abc import Iterator
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi.testclient import TestClient

from app import push
from app.main import app
from app.routers import push as push_router


def _raw_pub(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def _keypair_env(monkeypatch: pytest.MonkeyPatch) -> ec.EllipticCurvePrivateKey:
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setenv("VAPID_PRIVATE_KEY", push.b64u(key.private_numbers().private_value.to_bytes(32, "big")))
    monkeypatch.setenv("VAPID_PUBLIC_KEY", push.b64u(_raw_pub(key)))
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:team@example.com")
    return key


def test_rfc8291_appendix_a_vector() -> None:
    # RFC 8291 Appendix A: fixed application-server key and salt give this exact message
    as_key = ec.derive_private_key(int.from_bytes(push.unb64u("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1())
    body = push.encrypt(
        b"When I grow up, I want to be a watermelon",
        "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4",
        "BTBZMqHH6r4Tts7J_aSIgg", server_key=as_key, salt=push.unb64u("DGv6ra1nlYgDCS1FRnbzlw"),
    )
    assert push.b64u(body) == (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A"
        "_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
    )


def _ua_decrypt(body: bytes, ua: ec.EllipticCurvePrivateKey, auth: bytes) -> bytes:
    """The browser's side of RFC 8291, written out separately from app/push.py."""
    salt, rs, idlen = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    as_pub, ct = body[21:21 + idlen], body[21 + idlen:]
    assert rs == 4096 and idlen == 65 and len(ct) <= rs
    secret = ua.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
    kdf = lambda s, k, i, n: HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=i).derive(k)
    ikm = kdf(auth, secret, b"WebPush: info\x00" + _raw_pub(ua) + as_pub, 32)
    plain = AESGCM(kdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)).decrypt(kdf(salt, ikm, b"Content-Encoding: nonce\x00", 12), ct, None)
    assert plain.endswith(b"\x02")  # last-record delimiter, no padding
    return plain[:-1]


@pytest.mark.parametrize("size", [0, 1, 100, push.MAX_BODY])
def test_encrypt_round_trip_with_fresh_keys(size: int) -> None:
    ua, auth = ec.generate_private_key(ec.SECP256R1()), os.urandom(16)
    msg = os.urandom(size)
    a = push.encrypt(msg, push.b64u(_raw_pub(ua)), push.b64u(auth))
    b = push.encrypt(msg, push.b64u(_raw_pub(ua)), push.b64u(auth))
    assert _ua_decrypt(a, ua, auth) == msg and a != b  # fresh key and salt every time


def test_vapid_from_env_and_header(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    assert push.vapid_from_env() is None
    key = _keypair_env(monkeypatch)
    v = push.vapid_from_env()
    assert v is not None
    h = push.vapid_header("https://fcm.googleapis.com/fcm/send/abc", v, now=1_000_000)
    token, k = h.removeprefix("vapid t=").split(", k=")
    assert k == push.b64u(_raw_pub(key))
    claims = jwt.decode(token, key.public_key(), algorithms=["ES256"], audience="https://fcm.googleapis.com", options={"verify_exp": False})
    assert claims == {"aud": "https://fcm.googleapis.com", "exp": 1_000_000 + 12 * 3600, "sub": "mailto:team@example.com"}
    monkeypatch.setenv("VAPID_PUBLIC_KEY", push.b64u(_raw_pub(ec.generate_private_key(ec.SECP256R1()))))
    assert push.vapid_from_env() is None  # a public key from another pair would make every push fail
    _keypair_env(monkeypatch)
    monkeypatch.setenv("VAPID_SUBJECT", "team@example.com")
    assert push.vapid_from_env() is None  # push services require mailto: or https:
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:x@y.z")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "not-a-key!")
    assert push.vapid_from_env() is None


@pytest.mark.parametrize(("url", "ok"), [
    ("https://fcm.googleapis.com/fcm/send/x", True),
    ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
    ("https://web.push.apple.com/QG", True),
    ("https://wns2-pn1p.notify.windows.com/w/?token=x", True),
    ("http://fcm.googleapis.com/fcm/send/x", False),  # not https
    ("https://evil.example/fcm.googleapis.com", False),
    ("https://fcm.googleapis.com.evil.example/x", False),
    ("https://notfcm.googleapis.com/x", False),
    ("https://169.254.169.254/latest", False),
    ("https://[::1/", False),
    ("", False),
    ("https://evil.com\t.fcm.googleapis.com/x", False),  # urlsplit drops the tab; httpx would not
    ("https://evil.com\\.fcm.googleapis.com/x", False),
    ("https://evil.com\u2215.fcm.googleapis.com/x", False),  # division slash, not ASCII
    ("https://u:p@fcm.googleapis.com/x", False),  # user:password would replace the VAPID header
    ("https://fcm.googleapis.com:8443/x", False),
    ("https://fcm.googleapis.com:443/x", True),
    ("https://FCM.GOOGLEAPIS.COM/x", True),
    ("https://fcm.googleapis.com./x", False),
])
def test_only_browser_push_services(url: str, ok: bool) -> None:
    assert push.push_host_ok(url) is ok


def test_messages_for_reminders_and_checkins() -> None:
    p = {"title": "CRE assignment 3", "deadline_utc": "2026-10-30T17:00:00+00:00", "prep": "/#prep/abc"}
    assert push.message({"id": 7, "payload": p | {"slot": "t-1d"}}) == {
        "title": "StudyForge reminder", "body": "CRE assignment 3 is due tomorrow. Tap for your prep pack.", "url": "/#prep/abc"}
    assert push.message({"id": 7, "payload": p | {"slot": "checkin-2"}})["url"] == "/#prep/abc?checkin=7"
    long = push._payload({"title": "t", "body": "é" * 5000, "url": "/#prep/abc"})
    assert len(long) <= push.MAX_BODY and json.loads(long)["url"] == "/#prep/abc" and json.loads(long)["body"].endswith("…")


@pytest.mark.anyio
async def test_send_posts_an_encrypted_signed_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _keypair_env(monkeypatch)
    v = push.vapid_from_env()
    assert v is not None
    ua, auth = ec.generate_private_key(ec.SECP256R1()), os.urandom(16)
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "p256dh": push.b64u(_raw_pub(ua)), "auth": push.b64u(auth)}
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(201)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await push.send(client, sub, {"title": "T", "body": "B", "url": "/#"}, v) == 201
        assert await push.send(client, sub | {"endpoint": "https://evil.example/x"}, {"title": "T", "body": "B", "url": "/#"}, v) == 0
    assert len(seen) == 1  # the non-push host was never called
    req = seen[0]
    assert req.headers["content-encoding"] == "aes128gcm" and req.headers["ttl"] == str(push.TTL_S)
    assert req.headers["authorization"].startswith("vapid t=")
    assert json.loads(_ua_decrypt(req.content, ua, auth)) == {"title": "T", "body": "B", "url": "/#"}


# ---- routes (storage functions replaced; the real ones run against Postgres in tests/integration)

@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, dict[str, Any]]]:
    _keypair_env(monkeypatch)
    state: dict[str, Any] = {"saved": [], "removed": [], "notified": [], "full": False}

    async def save(engine: object, user: str, endpoint: str, p256dh: str, auth: str) -> bool:
        state["saved"].append((user, endpoint))
        return not state["full"]

    async def remove(engine: object, user: str, endpoint: str) -> bool:
        state["removed"].append((user, endpoint))
        return endpoint.endswith("mine")

    async def notify(engine: object, client: object, v: object, items: list[Any]) -> int:
        state["notified"].append(items)
        return 1

    monkeypatch.setattr(push, "save", save)
    monkeypatch.setattr(push, "remove", remove)
    monkeypatch.setattr(push, "notify", notify)
    push_router._tests.clear()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides |= {push_router.current_user: lambda: "u1", push_router.get_engine: lambda: object()}
    try:
        yield TestClient(app), state
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def _sub(endpoint: str = "https://fcm.googleapis.com/fcm/send/mine") -> dict[str, Any]:
    ua = ec.generate_private_key(ec.SECP256R1())
    return {"endpoint": endpoint, "expirationTime": None, "keys": {"p256dh": push.b64u(_raw_pub(ua)), "auth": push.b64u(os.urandom(16))}}


def test_key_subscribe_unsubscribe(client: tuple[TestClient, dict[str, Any]]) -> None:
    c, state = client
    assert c.get("/api/v1/push/key").json()["public_key"] == os.environ["VAPID_PUBLIC_KEY"]
    assert c.post("/api/v1/push/subscriptions", json=_sub()).status_code == 201
    assert state["saved"] == [("u1", "https://fcm.googleapis.com/fcm/send/mine")]
    state["full"] = True
    assert c.post("/api/v1/push/subscriptions", json=_sub()).status_code == 429
    assert c.delete("/api/v1/push/subscriptions", params={"endpoint": "https://fcm.googleapis.com/fcm/send/mine"}).status_code == 204
    assert c.delete("/api/v1/push/subscriptions", params={"endpoint": "https://fcm.googleapis.com/fcm/send/other"}).status_code == 404


@pytest.mark.parametrize("bad", [
    lambda s: s | {"endpoint": "https://evil.example/x"},
    lambda s: s | {"endpoint": "http://fcm.googleapis.com/x"},
    lambda s: s | {"keys": s["keys"] | {"p256dh": push.b64u(b"\x04" + b"a" * 63)}},
    lambda s: s | {"keys": s["keys"] | {"p256dh": "!!!"}},
    lambda s: s | {"keys": s["keys"] | {"p256dh": push.b64u(b"\x04" + b"\x01" * 64)}},  # right shape, not on the curve
    lambda s: s | {"keys": s["keys"] | {"auth": push.b64u(b"a" * 15)}},
    lambda s: s | {"keys": s["keys"] | {"user_id": "u2"}},
    lambda s: {"endpoint": s["endpoint"]},
])
def test_bad_subscriptions_refused(client: tuple[TestClient, dict[str, Any]], bad: Any) -> None:
    c, state = client
    assert c.post("/api/v1/push/subscriptions", json=bad(_sub())).status_code == 422
    assert state["saved"] == []


def test_test_notification_is_rate_limited(client: tuple[TestClient, dict[str, Any]]) -> None:
    c, state = client
    for _ in range(push_router.TESTS_PER_WINDOW):
        assert c.post("/api/v1/push/test").json() == {"sent": 1}
    assert c.post("/api/v1/push/test").status_code == 429
    assert state["notified"][0][0][0] == "u1"


def test_off_until_keys_are_set(client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    c, _ = client
    monkeypatch.delenv("VAPID_PRIVATE_KEY")
    assert c.get("/api/v1/push/key").status_code == 503
    assert c.post("/api/v1/push/subscriptions", json=_sub()).status_code == 503
    assert c.post("/api/v1/push/test").status_code == 503


def test_sign_in_required(monkeypatch: pytest.MonkeyPatch) -> None:
    _keypair_env(monkeypatch)
    c = TestClient(app)  # production wiring: auth.current_user, no token
    assert c.post("/api/v1/push/subscriptions", json=_sub()).status_code == 401
    assert c.delete("/api/v1/push/subscriptions", params={"endpoint": "x"}).status_code == 401
    assert c.post("/api/v1/push/test").status_code == 401


@pytest.mark.anyio
async def test_one_bad_device_never_stops_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    _keypair_env(monkeypatch)
    v = push.vapid_from_env()
    assert v is not None
    good = ec.generate_private_key(ec.SECP256R1())
    subs = [
        {"user_id": "u1", "endpoint": "https://fcm.googleapis.com/fcm/send/bad", "p256dh": push.b64u(b"\x04" + b"\x01" * 64), "auth": push.b64u(os.urandom(16))},
        {"user_id": "u1", "endpoint": "https://evil.com\t.fcm.googleapis.com/x", "p256dh": push.b64u(_raw_pub(good)), "auth": push.b64u(os.urandom(16))},
        {"user_id": "u2", "endpoint": "https://fcm.googleapis.com/fcm/send/good", "p256dh": push.b64u(_raw_pub(good)), "auth": push.b64u(os.urandom(16))},
    ]

    async def devices(engine: object, users: list[str]) -> list[dict[str, str]]:
        return [s for s in subs if s["user_id"] in users]

    monkeypatch.setattr(push, "devices", devices)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(201))) as client:
        msg = {"title": "T", "body": "B", "url": "/#"}
        assert await push.notify(object(), client, v, [("u1", msg), ("u2", msg)]) == 1  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_deliver_off_without_keys_and_skips_malformed_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(k, raising=False)
    assert await push.deliver(object(), [{"id": 1, "user_id": "u", "payload": {}}]) is None  # type: ignore[arg-type]
    _keypair_env(monkeypatch)
    seen: list[Any] = []

    async def notify(engine: object, client: object, v: object, items: list[Any]) -> int:
        seen.extend(items)
        return len(items)

    monkeypatch.setattr(push, "notify", notify)
    ok = {"id": 2, "user_id": "u", "payload": {"title": "T", "slot": "t-1d", "prep": "/#prep/a"}}
    assert await push.deliver(object(), [{"id": 1, "user_id": "u", "payload": {}}, ok]) == 1  # type: ignore[arg-type]
    assert [u for u, _ in seen] == ["u"]
    assert await push.deliver(object(), []) == 0  # type: ignore[arg-type]
