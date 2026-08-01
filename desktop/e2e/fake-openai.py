"""Minimal OpenAI-compatible endpoint used by the Windows desktop E2E test."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        payload = {
            "id": "windows-e2e",
            "object": "chat.completion",
            "created": 0,
            "model": "windows-e2e-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "OK"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18768), Handler).serve_forever()
