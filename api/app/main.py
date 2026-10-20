import json
import logging
import os
import re
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app import auth, db, wiring
from app.db import beat
from app.push import deliver
from app.reminders import drain, sweep
from app.routers import (
    checkins,
    dashboard,
    me,
    notes,
    notices,
    pdf,
    prep,
    progress,
    push,
    quiz_new,
    quizzes,
    solve,
    uploads,
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {"ts": self.formatTime(record), "level": record.levelname,
             "logger": record.name, "msg": record.getMessage()}
        )


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
# ponytail: root config at import; swap for dictConfig/per-request ids if needed
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)

app = FastAPI(title="StudyForge API")
# Bearer tokens, not cookies: no credentials. Never "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[  # trailing "/" and empty entries would silently never match
        o.strip().rstrip("/")
        for o in os.environ.get("CORS_ORIGINS", "https://studyforge-ten-alpha.vercel.app").split(",")
        if o.strip()
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

api_router = APIRouter()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/keepalive", methods=["GET", "HEAD"])  # UptimeRobot free tier may use HEAD
async def keepalive(response: Response, source: str = "") -> dict[str, str | bool | int | None]:
    if not os.environ.get("DATABASE_URL"):
        return {"status": "ok", "db": "off"}  # still wakes Render
    src = source if re.fullmatch(r"[a-z0-9-]{1,20}", source) else "unknown"
    try:
        wrote = await beat(db.shared_engine(), src)
    except Exception:
        logging.getLogger(__name__).exception("keepalive db check failed")
        response.status_code = 503
        return {"status": "error", "db": "down"}
    try:  # the ping is the scheduler clock: deliver due reminders (see app/reminders.py)
        due = await drain(db.shared_engine(), datetime.now(UTC))
        sent: int | None = len(due)
    except Exception:
        logging.getLogger(__name__).exception("keepalive drain failed")
        due, sent = [], None  # never hide the heartbeat result
    try:  # D1b: the same jobs as phone notifications (None = push not switched on)
        pushed: int | None = await deliver(db.shared_engine(), due)
    except Exception:
        logging.getLogger(__name__).exception("keepalive push failed")  # the in-app inbox still has them
        pushed = None
    try:  # ignored check-ins -> next round (the next ping delivers it if drain already ran)
        followups: int | None = await sweep(db.shared_engine(), datetime.now(UTC))
    except Exception:
        logging.getLogger(__name__).exception("keepalive sweep failed")
        followups = None
    return {"status": "ok", "db": "ok", "wrote": wrote, "sent": sent, "pushed": pushed, "followups": followups}


app.dependency_overrides[solve.current_user] = auth.current_user
app.dependency_overrides[solve.get_deps] = wiring.get_deps
app.include_router(solve.router)
app.dependency_overrides[checkins.get_engine] = db.shared_engine
app.include_router(checkins.router)
app.include_router(dashboard.router)
app.include_router(quizzes.router)  # shares checkins.get_engine
app.include_router(quiz_new.router)  # T1 POST /quizzes; shares prep.get_llm, uploads.get_storage_opt
app.include_router(progress.router)  # T4; shares checkins.get_engine, solve.current_user
app.include_router(notes.router)  # shares checkins.get_engine, solve.current_user, uploads.get_storage
app.dependency_overrides[prep.get_llm] = wiring.prep_llm
app.include_router(prep.router)  # D5; shares checkins.get_engine, solve.current_user
app.dependency_overrides[me.current_user] = auth.current_user
app.include_router(me.router)  # carries its own /api/v1 prefix, like solve.router
app.dependency_overrides[notices.current_user] = auth.current_user
app.include_router(notices.router)  # carries its own /api/v1 prefix, like solve.router
app.dependency_overrides[uploads.current_user] = auth.current_user
app.include_router(uploads.router)  # carries its own /api/v1 prefix
app.include_router(pdf.router)  # PY/TE PDF reading; uses uploads.current_user (overridden above)
app.dependency_overrides[push.current_user] = auth.current_user
app.include_router(push.router)  # carries its own /api/v1 prefix
app.include_router(api_router, prefix="/api/v1")
