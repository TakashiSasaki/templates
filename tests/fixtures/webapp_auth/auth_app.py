from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ACCESS_BY_PATH = {
    "/app": ("application", "application-user"),
    "/admin": ("admin", "admin"),
}
ALLOW_ADMIN_WITHOUT_ROLE = __ALLOW_ADMIN_WITHOUT_ROLE__
CLIENT_TEMPLATE = Path(__file__).with_name("client.html").read_text(encoding="utf-8")


def render_view(surface: str, state: str, message: str) -> bytes:
    return (
        CLIENT_TEMPLATE.replace("__SURFACE__", surface)
        .replace("__STATE__", state)
        .replace("__MESSAGE__", message)
        .encode("utf-8")
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def respond(self, status: int, surface: str, state: str, message: str) -> None:
        payload = render_view(surface, state, message)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            self.respond(200, "public", "populated", "Public home")
            return
        if path == "/status":
            self.respond(200, "status", "populated", "Service status")
            return
        if path not in ACCESS_BY_PATH:
            self.respond(404, "public", "not-found", "Route not found")
            return

        surface, required_role = ACCESS_BY_PATH[path]
        user = self.headers.get("X-User", "").strip()
        roles = {
            value.strip()
            for value in self.headers.get("X-Roles", "").split(",")
            if value.strip()
        }
        if not user:
            self.respond(401, surface, "unauthorized", "Sign in required")
            return

        if required_role not in roles and not (
            ALLOW_ADMIN_WITHOUT_ROLE and path == "/admin"
        ):
            self.respond(403, surface, "forbidden", "Access denied")
            return

        state = parse_qs(parsed.query).get("state", ["populated"])[0]
        if state == "loading":
            self.respond(200, surface, "loading", "Loading")
            return
        if state == "recoverable-error":
            self.respond(503, surface, "recoverable-error", "Retry available")
            return
        if state != "populated":
            self.respond(400, surface, "recoverable-error", "Unsupported state")
            return
        self.respond(200, surface, "populated", "Content available")


def make_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
