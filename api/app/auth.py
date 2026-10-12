"""Supabase JWT auth: verify the Bearer token against the project JWKS, return the user id.

Our project signs ES256; it does not use the legacy HS256 secret, so there is no HS256 path.
"""

import os

import httpx
import jwt
from fastapi import Header, HTTPException

_keys: dict[str, jwt.PyJWK] = {}  # ponytail: process-wide cache, no TTL — rotation handled by refetch-on-unknown-kid


def _base() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1"


def fetch_jwks() -> dict[str, jwt.PyJWK]:
    r = httpx.get(_base() + "/.well-known/jwks.json", timeout=5)
    r.raise_for_status()
    return {k["kid"]: jwt.PyJWK(k) for k in r.json()["keys"] if "kid" in k}


def _key(kid: str) -> jwt.PyJWK:
    if kid not in _keys:  # ponytail: one refetch per unknown kid; add a cooldown if junk kids ever hammer JWKS
        _keys.clear()
        _keys.update(fetch_jwks())
    return _keys[kid]


def current_user(authorization: str | None = Header(default=None)) -> str:
    try:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ValueError
        kid = jwt.get_unverified_header(token)["kid"]
        claims = jwt.decode(
            token,
            _key(kid).key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=_base(),
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        return str(claims["sub"])
    except Exception as err:  # any failure, incl. JWKS outage: generic 401, never leak why
        raise HTTPException(
            status_code=401,
            detail="invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err
