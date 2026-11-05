"""A tiny read-only web server for boards.

It serves only the study pages and the board JSON. It does not expose the
DeepTutor API, settings, API keys or any other file. By default it listens on
127.0.0.1 so only the laptop (or a phone over USB with ``adb reverse``) can
reach it.
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import socket
from urllib.parse import unquote, urlsplit

from .bundle import render_bundle
from .schema import BOARD_ID_PATTERN
from .store import BoardNotFound, BoardStore

DEFAULT_PORT = 8765
_ROUTE = re.compile(r"^/b/([a-z0-9][a-z0-9-]{0,79})\.(html|json)$")
_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def lan_address() -> str | None:
    """Best guess at this computer's address on the local network."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))  # no packet is sent
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def _index_page(store: BoardStore) -> str:
    rows = []
    for board in store.list():
        flag = "" if board.review.status == "reviewed" else " (draft)"
        rows.append(
            f'<li><a href="/b/{html.escape(board.board_id)}.html">'
            f"{html.escape(board.topic)}</a> "
            f"<small>{html.escape(board.subject)}{flag}</small></li>"
        )
    body = "<ul>" + "".join(rows) + "</ul>" if rows else "<p>No boards yet.</p>"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Learning boards</title>"
        "<style>body{font:18px/1.6 system-ui,sans-serif;margin:0;padding:16px;max-width:40rem}"
        "li{margin:12px 0}a{padding:8px 0;display:inline-block}</style></head>"
        f"<body><h1>Learning boards</h1>{body}</body></html>"
    )


def make_handler(store: BoardStore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BoardServer"
        sys_version = ""

        def _send(self, code: int, body: str, ctype: str) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", _CSP)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _handle(self) -> None:
            path = unquote(urlsplit(self.path).path)
            if path in ("/", "/index.html"):
                return self._send(200, _index_page(store), "text/html")
            match = _ROUTE.match(path)
            if not match or not BOARD_ID_PATTERN.match(match.group(1)):
                return self._send(404, "Not found", "text/plain")
            board_id, kind = match.groups()
            try:
                board = store.load(board_id)
            except BoardNotFound:
                return self._send(404, "Not found", "text/plain")
            except Exception:
                return self._send(500, "This board file is damaged.", "text/plain")
            if kind == "json":
                return self._send(
                    200,
                    json.dumps(board.model_dump(mode="json"), ensure_ascii=False),
                    "application/json",
                )
            return self._send(200, render_bundle(board, store.read_asset(board)), "text/html")

        def do_GET(self) -> None:  # noqa: N802
            self._handle()

        def do_HEAD(self) -> None:  # noqa: N802
            self._handle()

        def _refuse(self) -> None:
            self._send(405, "Read only", "text/plain")

        do_POST = do_PUT = do_DELETE = do_PATCH = _refuse  # noqa: N815

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

    return Handler


def make_server(
    store: BoardStore, host: str = "127.0.0.1", port: int = DEFAULT_PORT
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(store))


__all__ = ["DEFAULT_PORT", "lan_address", "make_server"]
