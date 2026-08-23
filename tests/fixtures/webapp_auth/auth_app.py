from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ACCESS_BY_PATH = {
    "/app": ("application", "application-user"),
    "/admin": ("admin", "admin"),
}
ROUTE_STATE_STATUS = {
    "loading": 200,
    "empty": 200,
    "populated": 200,
    "partial": 206,
    "recoverable-error": 503,
    "retrying": 202,
    "offline": 503,
}
STATE_PRESENTATION = {
    "loading": ("preserve", "polite", ()),
    "empty": ("main-heading", "polite", ("create", "change-filter")),
    "populated": ("preserve", "none", ()),
    "partial": ("preserve", "polite", ("retry-failed-part",)),
    "recoverable-error": ("error-summary", "assertive", ("retry", "edit-input")),
    "retrying": ("preserve", "polite", ("cancel-retry",)),
    "offline": ("preserve", "polite", ("retry-when-online",)),
    "unauthorized": ("main-heading", "assertive", ("sign-in",)),
    "forbidden": (
        "main-heading",
        "assertive",
        ("return-safe-route", "request-access"),
    ),
    "fatal-error": (
        "error-heading",
        "assertive",
        ("return-safe-route", "contact-support"),
    ),
    "not-found": ("main-heading", "assertive", ("return-home", "search")),
}
ALLOW_ADMIN_WITHOUT_ROLE = __ALLOW_ADMIN_WITHOUT_ROLE__
CLIENT_TEMPLATE = Path(__file__).with_name("client.html").read_text(encoding="utf-8")


def render_view(surface: str, state: str, message: str) -> bytes:
    focus_strategy, announcement, recovery_actions = STATE_PRESENTATION[state]
    aria_live = "off" if announcement == "none" else announcement
    return (
        CLIENT_TEMPLATE.replace("__SURFACE__", surface)
        .replace("__STATE__", state)
        .replace("__FOCUS_STRATEGY__", focus_strategy)
        .replace("__ANNOUNCEMENT__", aria_live)
        .replace("__RECOVERY_ACTIONS__", ",".join(recovery_actions))
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
        if path == "/__fatal":
            self.respond(500, "public", "fatal-error", "Fatal application error")
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
        if state not in ROUTE_STATE_STATUS:
            self.respond(400, surface, "recoverable-error", "Unsupported state")
            return
        status = ROUTE_STATE_STATUS[state]
        message = state.replace("-", " ").title()
        self.respond(status, surface, state, message)


def make_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
