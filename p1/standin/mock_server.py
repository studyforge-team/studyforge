"""Tiny OpenAI-compatible mock for testing check.py without a key or network.

    python p1/standin/mock_server.py [--port 8765] [--strict]

--strict answers 400 to any request carrying chat_template_kwargs (the Nemotron
thinking flag), like a provider that rejects unknown fields. Canned replies only.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

STRICT = False


def reply(body: dict[str, Any]) -> dict[str, Any]:
    msgs = body.get("messages", [])
    last = msgs[-1]["content"] if msgs else ""
    text = json.dumps(last)
    message: dict[str, Any] = {"role": "assistant", "content": "OK"}
    if body.get("tools"):
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "run_python",
                        "arguments": json.dumps({"code": "result = {'F': 6}"}),
                    },
                }
            ],
        }
    elif "image_url" in text:
        message["content"] = "A 2 kg mass accelerates at 3 m/s^2. Find F."
    elif "Classify" in text or "schema" in text.lower():
        message["content"] = '{"kind": "concept"}'
    return {
        "id": "mock",
        "object": "chat.completion",
        "created": 0,
        "model": body.get("model", "mock"),
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict[str, Any]) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._send(
            200, {"object": "list", "data": [{"id": "mock-model", "object": "model"}]}
        )

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if STRICT and "chat_template_kwargs" in body:
            self._send(
                400, {"error": {"message": "Unknown field: chat_template_kwargs"}}
            )
            return
        self._send(200, reply(body))

    def log_message(self, *args: Any) -> None:
        return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    STRICT = a.strict
    HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
