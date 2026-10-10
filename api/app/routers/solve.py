"""Solve endpoints (master plan §3.5): POST /solve, POST /solve/{id}/result,
GET /solve/{id} (requested addition: re-fetch the pending step after a restart).

Wiring is injected so this router works before the app skeleton (A2), the auth
backend and the Postgres store exist: the app sets
    app.dependency_overrides[get_deps] = lambda: deps
    app.dependency_overrides[current_user] = <auth dependency>
Locally, `dev_user` can stand in for auth.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from app.agent import loop
from app.agent.loop import Deps
from app.agent.state import SolveNotFound
from app.agent.steps import ResultBody

MAX_RESULT_BODY = 3 * 1024 * 1024  # 4 PNGs of 500 KB as base64 + stdout + result

router = APIRouter(prefix="/api/v1")


class SolveRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    upload_id: str | None = None
    confirmed: bool = False


def get_deps() -> Deps:
    raise RuntimeError("app must override get_deps with the configured Deps")


def current_user() -> str:
    raise HTTPException(status_code=401, detail="not signed in")


def dev_user() -> str:
    """Local development only: every request is the same user."""
    return "dev-user"


DepsDep = Annotated[Deps, Depends(get_deps)]
UserDep = Annotated[str, Depends(current_user)]


@router.post("/solve")
async def start_solve(
    req: SolveRequest, deps: DepsDep, user: UserDep
) -> dict[str, Any]:
    solve_id, step = await loop.start(
        req.question,
        deps,
        user_id=user,
        upload_id=req.upload_id,
        confirmed=req.confirmed,
    )
    return {"solve_id": solve_id, "step": step}


@router.post("/solve/{solve_id}/result")
async def post_result(
    solve_id: str, request: Request, deps: DepsDep, user: UserDep
) -> dict[str, Any]:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_RESULT_BODY:
        raise HTTPException(status_code=413, detail="result body too large")
    raw = await request.body()
    if len(raw) > MAX_RESULT_BODY:
        raise HTTPException(status_code=413, detail="result body too large")
    try:
        body = ResultBody.model_validate_json(raw)
    except ValidationError as err:
        raise HTTPException(status_code=422, detail="invalid result body") from err
    try:
        return {"step": await loop.on_result(solve_id, user, body, deps)}
    except SolveNotFound as err:
        raise HTTPException(status_code=404, detail="solve not found") from err


@router.get("/solve/{solve_id}")
async def get_solve_step(solve_id: str, deps: DepsDep, user: UserDep) -> dict[str, Any]:
    try:
        return {"step": await loop.get_step(solve_id, user, deps)}
    except SolveNotFound as err:
        raise HTTPException(status_code=404, detail="solve not found") from err
