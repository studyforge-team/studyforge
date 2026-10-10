"""Record/replay HTTP transport so CI can run model-dependent tests with no API key.

Fixtures are keyed by the request's method, URL path and sorted JSON body. Headers
(which carry the API key) and the host never enter the key or the fixture.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

import httpx


class MissingFixture(Exception):
    def __init__(self, key: str, path: Path, body: Any) -> None:
        excerpt = json.dumps(body, sort_keys=True)[:300]
        super().__init__(
            f"no fixture {key[:12]} at {path}; re-record with TF_RECORD=1. "
            f"Request body: {excerpt}"
        )


def _parse(content: bytes) -> Any:
    return json.loads(content) if content else None


class ReplayTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        mode: Literal["replay", "record"],
        fixtures_dir: Path,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.mode = mode
        self.fixtures_dir = fixtures_dir
        self.inner = inner or (httpx.AsyncHTTPTransport() if mode == "record" else None)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req = {
            "method": request.method,
            "path": request.url.path,
            "body": _parse(request.content),
        }
        canon = json.dumps(req, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(canon.encode()).hexdigest()
        path = self.fixtures_dir / key[:2] / f"{key}.json"
        if self.mode == "replay":
            if not path.exists():
                raise MissingFixture(key, path, req["body"])
            saved = json.loads(path.read_text())["response"]
            return httpx.Response(
                saved["status"],
                headers=saved["headers"],
                content=json.dumps(saved["body"]).encode(),
            )
        assert self.inner is not None
        resp = await self.inner.handle_async_request(request)
        raw = await resp.aread()
        if 200 <= resp.status_code < 300:
            headers = {"content-type": resp.headers.get("content-type", "")}
            fixture = {
                "request": req,
                "response": {
                    "status": resp.status_code,
                    "headers": headers,
                    "body": _parse(raw),
                },
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
        return httpx.Response(resp.status_code, headers=resp.headers, content=raw)


def replay_client(fixtures_dir: Path) -> httpx.AsyncClient:
    """TF_RECORD=1 records against the real API; otherwise replay, never the network."""
    mode: Literal["replay", "record"] = (
        "record" if os.environ.get("TF_RECORD") == "1" else "replay"
    )
    return httpx.AsyncClient(transport=ReplayTransport(mode, fixtures_dir))
