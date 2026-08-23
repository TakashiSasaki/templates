from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROLE_BY_PATH = {
    "/app": "application-user",
    "/admin": "admin",
}
ALLOW_ADMIN_WITHOUT_ROLE = __ALLOW_ADMIN_WITHOUT_ROLE__


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def respond(self, status: int, body: str) -> None:
        payload = (body + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            self.respond(200, "public:populated")
            return
        if path == "/status":
            self.respond(200, "status:populated")
            return
        if path not in ROLE_BY_PATH:
            self.respond(404, "not-found")
            return

        user = self.headers.get("X-User", "").strip()
        roles = {
            value.strip()
            for value in self.headers.get("X-Roles", "").split(",")
            if value.strip()
        }
        if not user:
            self.respond(401, "unauthorized")
            return

        required_role = ROLE_BY_PATH[path]
        if required_role not in roles and not (
            ALLOW_ADMIN_WITHOUT_ROLE and path == "/admin"
        ):
            self.respond(403, "forbidden")
            return

        state = parse_qs(parsed.query).get("state", ["populated"])[0]
        if state == "loading":
            self.respond(200, path.removeprefix("/") + ":loading")
            return
        if state == "recoverable-error":
            self.respond(503, "recoverable-error")
            return
        if state != "populated":
            self.respond(400, "unsupported-state")
            return
        self.respond(200, path.removeprefix("/") + ":populated")


def make_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
