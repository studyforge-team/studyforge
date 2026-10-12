import json
import logging
import os

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
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


app.dependency_overrides[solve.current_user] = auth.current_user
# solve.router is NOT included yet: it also needs get_deps (LLM/store wiring, a P1/P2 decision).
app.include_router(api_router, prefix="/api/v1")
