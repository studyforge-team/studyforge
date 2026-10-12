import json
import logging

from fastapi import APIRouter, FastAPI


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

api_router = APIRouter()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
