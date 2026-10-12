import json
import logging
import os

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
        )


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(
    level=logging.INFO,
    handlers=[_handler],
    force=True,
)

app = FastAPI(title="StudyForge API")

# Read allowed frontend origins from the environment.
# Multiple origins can be comma-separated.
origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGIN",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

api_router = APIRouter()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
