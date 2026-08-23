from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def body(self, status: int, text: str) -> None:
        payload = (text + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/app":
            user = self.headers.get("X-User", "").strip()
            roles = {
                value.strip()
                for value in self.headers.get("X-Roles", "").split(",")
                if value.strip()
            }
            if not user:
                destination = "/sign-in?returnTo=" + quote("/app", safe="")
                self.send_response(302)
                self.send_header("Location", destination)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if "application-user" not in roles:
                self.body(403, "forbidden")
                return
            self.body(200, "application:populated")
            return

        if parsed.path == "/sign-in":
            return_to = parse_qs(parsed.query).get("returnTo", [""])[0]
            self.body(200, "sign-in:return-to=" + return_to)
            return

        self.body(404, "not-found")


def make_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
