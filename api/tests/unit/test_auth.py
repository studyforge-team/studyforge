import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from test_loop import Clock
from test_solve_routes import script

from app import auth
from app.agent.loop import Deps
from app.agent.state import InMemoryStore
from app.routers import solve

URL = "https://proj.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER = ec.generate_private_key(ec.SECP256R1())


def jwk(key: Any, kid: str = "k1") -> dict[str, Any]:
    d = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    return {**d, "kid": kid, "alg": "ES256", "use": "sig"}


def mint(sub: str = "A", key: Any = KEY, alg: str = "ES256", kid: str = "k1", **over: Any) -> str:
    claims = {"sub": sub, "aud": "authenticated", "iss": URL + "/auth/v1",
              "exp": int(time.time()) + 600, "role": "authenticated", **over}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


@pytest.fixture(autouse=True)
def jwks(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setattr(auth, "_keys", {})
    monkeypatch.setattr(auth, "_fetched_at", None)
    calls: list[int] = []

    def fake() -> dict[str, jwt.PyJWK]:
        calls.append(1)
        return {"k1": jwt.PyJWK(jwk(KEY))}

    monkeypatch.setattr(auth, "fetch_jwks", fake)
    return calls


def app_with_auth() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    def me(user: str = Depends(auth.current_user)) -> str:
        return user

    return app


def get(token: str | None) -> Any:
    h = {} if token is None else {"Authorization": f"Bearer {token}"}
    return TestClient(app_with_auth()).get("/me", headers=h)


def test_valid_token_returns_sub() -> None:
    r = get(mint("user-1"))
    assert r.status_code == 200 and r.json() == "user-1"


def test_anonymous_user_is_valid() -> None:
    assert get(mint("anon-1", is_anonymous=True)).json() == "anon-1"


def forged_none() -> str:
    claims = {"sub": "A", "aud": "authenticated", "iss": URL + "/auth/v1", "exp": int(time.time()) + 600}
    return jwt.encode(claims, None, algorithm="none", headers={"kid": "k1"})


@pytest.mark.parametrize("token", [
    None,
    "not-a-jwt",
    mint(exp=int(time.time()) - 10),
    mint(aud="other"),
    mint(iss="https://evil.example/auth/v1"),
    mint(key=OTHER),
    mint(key="secret" * 8, alg="HS256"),
    forged_none(),
])
def test_bad_tokens_are_401(token: str | None) -> None:
    r = get(token)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json() == {"detail": "invalid or missing token"}


def test_unknown_kid_refetches_once(jwks: list[int], monkeypatch: pytest.MonkeyPatch) -> None:
    assert get(mint(kid="rotated")).status_code == 401  # still unknown after refetch
    assert len(jwks) == 1
    assert get(mint(kid="junk")).status_code == 401
    assert len(jwks) == 1  # cooldown: a junk kid right after a fetch doesn't refetch
    monkeypatch.setattr(auth, "fetch_jwks", lambda: {"rotated": jwt.PyJWK(jwk(KEY, "rotated"))})
    monkeypatch.setattr(auth, "_fetched_at", time.monotonic() - 61)  # cooldown elapsed
    assert get(mint(kid="rotated")).status_code == 200  # rotation picked up
    assert get(mint(kid="rotated")).status_code == 200  # cached, no further fetch needed


def test_anonymous_claim_reaches_request_state() -> None:
    app = FastAPI()

    @app.get("/anon")
    def anon(request: Request, user: str = Depends(auth.current_user)) -> bool:
        return bool(request.state.anon)

    h = lambda t: {"Authorization": f"Bearer {t}"}
    c = TestClient(app)
    assert c.get("/anon", headers=h(mint("a", is_anonymous=True))).json() is True
    assert c.get("/anon", headers=h(mint("b"))).json() is False


def test_user_b_cannot_read_user_a_solve_404_not_403() -> None:
    deps = Deps(llm=script(), store=InMemoryStore(), clock=Clock())
    app = FastAPI()
    app.include_router(solve.router)
    app.dependency_overrides[solve.get_deps] = lambda: deps
    app.dependency_overrides[solve.current_user] = auth.current_user
    http = TestClient(app)
    ha, hb = ({"Authorization": f"Bearer {mint(u)}"} for u in ("A", "B"))
    sid = http.post("/api/v1/solve", json={"question": "Find X"}, headers=ha).json()["solve_id"]
    assert http.get(f"/api/v1/solve/{sid}", headers=ha).status_code == 200
    assert http.get(f"/api/v1/solve/{sid}", headers=hb).status_code == 404  # hides existence; stricter than 403
    assert http.get(f"/api/v1/solve/{sid}").status_code == 401

