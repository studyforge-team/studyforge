"""Phone reminders (D1b): the browser subscribes to web push; app/push.py sends.

GET    /api/v1/push/key                        -> {public_key} (503 until VAPID keys are set on the host)
POST   /api/v1/push/subscriptions {endpoint, keys: {p256dh, auth}} -> 201 (this device now gets your reminders)
DELETE /api/v1/push/subscriptions?endpoint=…   -> 204 (turn off on this device; 404 if not yours)
POST   /api/v1/push/test                       -> {sent: n} (a test notification to your devices)
"""

import os
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncEngine

from app import push
from app.db import shared_engine

router = APIRouter(prefix="/api/v1")
TESTS_PER_WINDOW, TEST_WINDOW_S = 3, 600  # a test button must not become a way to spam push services
_tests: dict[str, list[float]] = {}  # ponytail: per process; Render free runs one


def current_user() -> str:  # main.py overrides with auth.current_user (same pattern as solve.py)
    raise HTTPException(status_code=401, detail="not signed in")


def get_engine() -> AsyncEngine:
    if not os.environ.get("DATABASE_URL"):
        raise HTTPException(503, "not available")
    return shared_engine()


def get_vapid() -> push.Vapid:
    v = push.vapid_from_env()
    if v is None:
        raise HTTPException(503, "phone reminders are not switched on")
    return v


UserDep = Annotated[str, Depends(current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
VapidDep = Annotated[push.Vapid, Depends(get_vapid)]


class Keys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)

    @field_validator("p256dh")
    @classmethod
    def _point(cls, v: str) -> str:  # checked here, so a bad key never reaches a send
        if not push.valid_point(v):
            raise ValueError("p256dh is not a P-256 public key")
        return v

    @field_validator("auth")
    @classmethod
    def _secret(cls, v: str) -> str:
        try:
            ok = len(push.unb64u(v)) == 16
        except ValueError:
            ok = False
        if not ok:
            raise ValueError("auth is not a 16-byte secret")
        return v


class Subscription(BaseModel):
    model_config = ConfigDict(extra="ignore")  # PushSubscription.toJSON() also has expirationTime
    endpoint: str = Field(max_length=1000)
    keys: Keys

    @field_validator("endpoint")
    @classmethod
    def _host(cls, v: str) -> str:
        if not push.push_host_ok(v):
            raise ValueError("not a browser push service")
        return v


@router.get("/push/key")
def public_key(v: VapidDep) -> dict[str, str]:
    return {"public_key": v.public_b64}


@router.post("/push/subscriptions", status_code=201)
async def subscribe(user: UserDep, body: Subscription, engine: EngineDep, _v: VapidDep) -> dict[str, bool]:
    if not await push.save(engine, user, body.endpoint, body.keys.p256dh, body.keys.auth):
        raise HTTPException(429, f"reminders are on for {push.MAX_DEVICES} devices already")
    return {"ok": True}


@router.delete("/push/subscriptions", status_code=204)
async def unsubscribe(user: UserDep, endpoint: str, engine: EngineDep) -> Response:
    if not await push.remove(engine, user, endpoint):
        raise HTTPException(404, "not subscribed")  # also another user's device: never says which
    return Response(status_code=204)


@router.post("/push/test")
async def test(user: UserDep, engine: EngineDep, v: VapidDep) -> dict[str, int]:
    now = time.monotonic()
    for u in [u for u, ts in _tests.items() if now - ts[-1] >= TEST_WINDOW_S]:
        del _tests[u]  # forget users whose last test is out of the window
    recent = [t for t in _tests.get(user, []) if now - t < TEST_WINDOW_S]
    if len(recent) >= TESTS_PER_WINDOW:
        raise HTTPException(429, "try the test again in a few minutes")
    _tests[user] = [*recent, now]
    msg = {"title": "StudyForge", "body": "Phone reminders are on. Tap to open StudyForge.", "url": "/#"}
    async with httpx.AsyncClient(timeout=10) as client:
        return {"sent": await push.notify(engine, client, v, [(user, msg)])}
