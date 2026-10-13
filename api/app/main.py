import json
import logging
import os
import re

from fastapi import APIRouter, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.db import beat, make_engine
from app.routers import solve


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
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

api_router = APIRouter()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/keepalive", methods=["GET", "HEAD"])  # UptimeRobot free tier may use HEAD
async def keepalive(response: Response, source: str = "") -> dict[str, str | bool]:
    if not os.environ.get("DATABASE_URL"):
        return {"status": "ok", "db": "off"}  # still wakes Render
    src = source if re.fullmatch(r"[a-z0-9-]{1,20}", source) else "unknown"
    # ponytail: engine per call (+dispose) — a module-level one would be bound to the first event
    # loop; at one ping per 5 min the connect cost is irrelevant. Share one if traffic grows.
    engine = make_engine()
    try:
        return {"status": "ok", "db": "ok", "wrote": await beat(engine, src)}
    except Exception:
        logging.getLogger(__name__).exception("keepalive db check failed")
        response.status_code = 503
        return {"status": "error", "db": "down"}
    finally:
        await engine.dispose()


app.dependency_overrides[solve.current_user] = auth.current_user
# solve.router is NOT included yet: it also needs get_deps (LLM/store wiring, a P1/P2 decision).
app.include_router(api_router, prefix="/api/v1")
