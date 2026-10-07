"""Сервис песочницы: HTTP-обёртка над runner.py (только стандартная библиотека Python).

Работает в отдельном контейнере без сети: принимает задания от бэкенда через Unix-сокет на общем томе
(SANDBOX_SOCKET; без него — TCP-порт PORT), проверяет токен, ограничивает размер запроса и число одновременных
запусков. Проверка здоровья для Docker: python server.py --health.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from runner import available_languages, run

SOCKET = os.environ.get("SANDBOX_SOCKET")
PORT = int(os.environ.get("PORT", "8100"))
TOKEN = os.environ.get("SANDBOX_TOKEN", "")
SEM = threading.BoundedSemaphore(int(os.environ.get("SANDBOX_CONCURRENCY", "2")))
MAX_BODY = 256_000


class Handler(BaseHTTPRequestHandler):
    server_version = "fsp-sandbox/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "languages": available_languages()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            return self._send(404, {"error": "not found"})
        if TOKEN and self.headers.get("X-Sandbox-Token") != TOKEN:
            return self._send(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {"error": "request too large"})
        try:
            req = json.loads(self.rfile.read(length))
            args = {k: req[k] for k in ("language", "code", "entrypoint", "inputs")}
            args["time_limit_ms"] = max(200, min(10_000, int(req.get("time_limit_ms", 2000))))
        except (ValueError, KeyError, TypeError):
            return self._send(400, {"error": "bad request"})
        with SEM:
            result = run(**args)
        self._send(200, result)

    def log_message(self, fmt: str, *args) -> None:  # тихий журнал: код кандидатов не логируется
        pass


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve() -> None:
    if SOCKET:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(SOCKET)
        srv = UnixHTTPServer(SOCKET, Handler)
        os.chmod(SOCKET, 0o666)  # бэкенд работает под другим пользователем
    else:
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.serve_forever()


def health() -> int:
    """GET /health через тот же транспорт, по которому обращается бэкенд."""
    s = socket.socket(socket.AF_UNIX) if SOCKET else socket.socket()
    s.settimeout(3)
    try:
        s.connect(SOCKET or ("127.0.0.1", PORT))
        s.sendall(b"GET /health HTTP/1.0\r\n\r\n")
        return 0 if s.recv(64).split(b" ")[1:2] == [b"200"] else 1
    except OSError:
        return 1
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(health()) if "--health" in sys.argv else serve()
