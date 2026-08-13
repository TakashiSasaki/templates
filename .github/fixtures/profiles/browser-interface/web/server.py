#!/usr/bin/env python3
"""Loopback-only browser verification server for the browser-interface fixture."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import signal
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from text_stats import CONTRACT_VERSION, analyze  # noqa: E402

MAX_BODY_BYTES = 64 * 1024
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 4567
DEFAULT_PID_FILE = "tmp/text-stats-web.pid"
DISABLED_EXIT = 78
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
HTML = b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Text statistics verification</title>
  <link rel="stylesheet" href="/app.css">
</head>
<body>
  <main>
    <h1>Text statistics verification</h1>
    <p>This loopback-only page computes byte, line, and word counts without retaining the submitted text.</p>
    <form id="stats-form">
      <label for="text">Text</label>
      <textarea id="text" name="text" required></textarea>
      <button type="submit">Compute</button>
    </form>
    <pre id="result" aria-live="polite"></pre>
  </main>
  <script src="/app.js" defer></script>
</body>
</html>
"""
JAVASCRIPT = b'''"use strict";
const form = document.getElementById("stats-form");
const result = document.getElementById("result");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  result.textContent = "Working...";
  try {
    const response = await fetch("/api/text-stats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: document.getElementById("text").value })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Request failed");
    result.textContent = JSON.stringify(payload.result, null, 2);
  } catch (error) {
    result.textContent = `Error: ${error.message}`;
  }
});
'''
CSS = b""":root { color-scheme: light dark; font-family: system-ui, sans-serif; }
body { margin: 0; padding: 2rem; }
main { max-width: 48rem; margin: 0 auto; }
textarea { box-sizing: border-box; display: block; min-height: 12rem; width: 100%; margin: 0.5rem 0 1rem; }
button { padding: 0.5rem 1rem; }
pre { min-height: 5rem; padding: 1rem; border: 1px solid currentColor; overflow: auto; }
"""
STATIC_RESPONSES = {
    "/": (HTML, "text/html; charset=utf-8"),
    "/app.js": (JAVASCRIPT, "text/javascript; charset=utf-8"),
    "/app.css": (CSS, "text/css; charset=utf-8"),
}
KNOWN_PATHS = {*STATIC_RESPONSES, "/healthz", "/api/text-stats"}


class ConfigurationError(RuntimeError):
    pass


class RequestError(RuntimeError):
    def __init__(
        self,
        status: int,
        message: str,
        *,
        close_connection: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.close_connection = close_connection


class BrowserHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], diagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(address, BrowserHandler)


class BrowserHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TextStatsWeb/1"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    @property
    def diagnostic(self):
        return self.server.diagnostic  # type: ignore[attr-defined]

    @property
    def active_port(self) -> int:
        return int(self.server.server_address[1])

    def do_GET(self) -> None:  # noqa: N802
        self._service("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._service("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._service("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._service("DELETE")

    def __getattr__(self, name: str):
        if name.startswith("do_"):
            return lambda: self._service(self.command)
        raise AttributeError(name)

    def _service(self, method: str) -> None:
        status = 500
        request_path = urlsplit(self.path).path
        try:
            request_origin = self._authorize_host()
            if method == "GET" and request_path in STATIC_RESPONSES:
                body, content_type = STATIC_RESPONSES[request_path]
                status = 200
                self._respond(status, content_type, body)
            elif method == "GET" and request_path == "/healthz":
                status = 200
                self._respond_json(status, {"ok": True, "interface": "web"})
            elif method == "POST" and request_path == "/api/text-stats":
                raw = self._read_bounded_body()
                self._authorize_origin(request_origin)
                status, payload = self._handle_stats(raw)
                self._respond_json(status, payload)
            elif request_path in KNOWN_PATHS:
                status = 405
                allow = "POST" if request_path == "/api/text-stats" else "GET"
                self._respond_json(
                    status,
                    {"ok": False, "error": "method not allowed"},
                    extra_headers={"Allow": allow},
                )
            else:
                status = 404
                self._respond_json(status, {"ok": False, "error": "not found"})
        except RequestError as exc:
            status = exc.status
            should_close = exc.close_connection or status == 413
            extra_headers = {"Connection": "close"} if should_close else None
            if should_close:
                self.close_connection = True
            self._respond_json(
                status,
                {"ok": False, "error": str(exc)},
                extra_headers=extra_headers,
            )
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            print(
                f"web request failed: {type(exc).__name__}: {exc}",
                file=self.diagnostic,
                flush=True,
            )
            status = 500
            try:
                self._respond_json(
                    status, {"ok": False, "error": "internal server error"}
                )
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
        finally:
            print(
                f"web request {method} {request_path} -> {status}",
                file=self.diagnostic,
                flush=True,
            )

    def _authorize_host(self) -> tuple[str, int]:
        authority = _parse_authority(self.headers.get("Host", ""))
        if authority is None or authority[0] not in {"127.0.0.1", "localhost"}:
            raise RequestError(403, "forbidden host")
        if authority[1] != self.active_port:
            raise RequestError(403, "forbidden host")
        return authority

    def _authorize_origin(self, request_origin: tuple[str, int]) -> None:
        origin = _parse_origin(self.headers.get("Origin", ""))
        if origin != request_origin:
            raise RequestError(403, "same-origin browser request required")

    def _handle_stats(self, raw: bytes) -> tuple[int, dict[str, object]]:
        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise RequestError(415, "application/json is required")

        try:
            text = raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise RequestError(400, "request body is not valid UTF-8") from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RequestError(400, "invalid JSON request body") from exc
        if (
            type(payload) is not dict
            or list(payload.keys()) != ["text"]
            or type(payload.get("text")) is not str
        ):
            raise RequestError(
                422, "request must contain only one string field named text"
            )
        submitted_text = payload["text"]
        try:
            submitted_text.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise RequestError(
                400, "request text contains an invalid Unicode scalar value"
            ) from exc
        return (
            200,
            {
                "contractVersion": CONTRACT_VERSION,
                "ok": True,
                "result": analyze(submitted_text),
            },
        )

    def _read_bounded_body(self) -> bytes:
        transfer_values = self.headers.get_all("Transfer-Encoding") or []
        content_lengths = self.headers.get_all("Content-Length") or []

        if transfer_values and content_lengths:
            raise RequestError(
                400,
                "ambiguous request framing",
                close_connection=True,
            )

        if transfer_values:
            if (
                len(transfer_values) != 1
                or transfer_values[0].strip().lower() != "chunked"
            ):
                raise RequestError(
                    400,
                    "unsupported transfer encoding",
                    close_connection=True,
                )
            return self._read_chunked_body()

        if not content_lengths:
            raise RequestError(
                411,
                "Content-Length or chunked Transfer-Encoding is required",
                close_connection=True,
            )
        if len(content_lengths) != 1:
            raise RequestError(
                400,
                "ambiguous Content-Length",
                close_connection=True,
            )

        content_length = content_lengths[0].strip()
        if not content_length.isascii() or not content_length.isdigit():
            raise RequestError(
                400,
                "invalid Content-Length",
                close_connection=True,
            )
        length = int(content_length, 10)
        if length > MAX_BODY_BYTES:
            raise RequestError(
                413,
                "request body exceeds 65536 bytes",
                close_connection=True,
            )
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestError(
                400,
                "incomplete request body",
                close_connection=True,
            )
        return body

    def _read_chunked_body(self) -> bytes:
        body = bytearray()
        while True:
            line = self.rfile.readline(4097)
            if not line or len(line) > 4096 or not line.endswith(b"\n"):
                raise RequestError(
                    400,
                    "invalid chunked request body",
                    close_connection=True,
                )
            token = line.strip().split(b";", 1)[0]
            try:
                size = int(token, 16)
            except ValueError as exc:
                raise RequestError(
                    400,
                    "invalid chunked request body",
                    close_connection=True,
                ) from exc
            if size < 0:
                raise RequestError(
                    400,
                    "invalid chunked request body",
                    close_connection=True,
                )
            if size == 0:
                while True:
                    trailer = self.rfile.readline(4097)
                    if not trailer or len(trailer) > 4096:
                        raise RequestError(
                            400,
                            "invalid chunked request body",
                            close_connection=True,
                        )
                    if trailer in {b"\r\n", b"\n"}:
                        return bytes(body)
            if len(body) + size > MAX_BODY_BYTES:
                raise RequestError(
                    413,
                    "request body exceeds 65536 bytes",
                    close_connection=True,
                )
            chunk = self.rfile.read(size)
            if len(chunk) != size:
                raise RequestError(
                    400,
                    "incomplete chunked request body",
                    close_connection=True,
                )
            if self.rfile.read(2) != b"\r\n":
                raise RequestError(
                    400,
                    "invalid chunked request body",
                    close_connection=True,
                )
            body.extend(chunk)

    def _respond_json(
        self,
        status: int,
        payload: dict[str, object],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        self._respond(
            status,
            "application/json; charset=utf-8",
            body,
            extra_headers=extra_headers,
        )

    def _respond(
        self,
        status: int,
        content_type: str,
        body: bytes,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()


def _parse_authority(value: str) -> tuple[str, int] | None:
    if not value or any(character.isspace() for character in value):
        return None
    try:
        parsed = urlsplit("http://" + value)
        if (
            parsed.scheme != "http"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.hostname is None
            or parsed.path != ""
            or parsed.query
            or parsed.fragment
        ):
            return None
        return parsed.hostname.lower(), parsed.port if parsed.port is not None else 80
    except ValueError:
        return None


def _parse_origin(value: str) -> tuple[str, int] | None:
    if not value or any(character.isspace() for character in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.hostname is None
            or parsed.path != ""
            or parsed.query
            or parsed.fragment
        ):
            return None
        return parsed.hostname.lower(), parsed.port if parsed.port is not None else 80
    except ValueError:
        return None


def process_start_ticks(pid: int) -> str | None:
    try:
        content = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    close = content.rfind(")")
    if close < 0:
        return None
    fields = content[close + 2 :].split()
    if len(fields) < 20 or not fields[19].isdigit():
        return None
    return fields[19]


def pid_record(pid: int | None = None) -> dict[str, object]:
    actual_pid = os.getpid() if pid is None else pid
    ticks = process_start_ticks(actual_pid)
    if ticks is None:
        raise ConfigurationError("unable to read current process identity")
    return {"pid": actual_pid, "startTicks": ticks}


def read_pid_record(path: Path) -> dict[str, object]:
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ConfigurationError(
                f"Web UI PID file must be a regular non-symlink file: {path}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ConfigurationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Web UI PID file is invalid: {path}") from exc
    if (
        type(payload) is not dict
        or set(payload) != {"pid", "startTicks"}
        or type(payload["pid"]) is not int
        or payload["pid"] <= 0
        or type(payload["startTicks"]) is not str
        or not payload["startTicks"].isdigit()
    ):
        raise ConfigurationError(f"Web UI PID file is invalid: {path}")
    return payload


def write_pid_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ConfigurationError(f"Web UI PID file already exists: {path}")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            payload = (json.dumps(record, separators=(",", ":")) + "\n").encode()
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except FileExistsError as exc:
        raise ConfigurationError(f"Web UI PID file already exists: {path}") from exc
    except OSError as exc:
        raise ConfigurationError(f"unable to create Web UI PID file {path}: {exc}") from exc


def configuration(environment: dict[str, str]) -> dict[str, object]:
    bind = environment.get("TEXT_STATS_WEB_BIND", DEFAULT_BIND)
    if bind != DEFAULT_BIND:
        raise ConfigurationError("TEXT_STATS_WEB_BIND must be 127.0.0.1")
    raw_port = environment.get("TEXT_STATS_WEB_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port, 10)
    except ValueError as exc:
        raise ConfigurationError(
            "TEXT_STATS_WEB_PORT must be an integer between 0 and 65535"
        ) from exc
    if not 0 <= port <= 65535:
        raise ConfigurationError("TEXT_STATS_WEB_PORT must be between 0 and 65535")
    raw_pid = environment.get("TEXT_STATS_WEB_PID_FILE", DEFAULT_PID_FILE)
    return {
        "bind": bind,
        "port": port,
        "pid_file": Path(os.path.abspath(raw_pid)),
    }


def health(config: dict[str, object]) -> int:
    connection = http.client.HTTPConnection(
        str(config["bind"]), int(config["port"]), timeout=1.0
    )
    try:
        connection.request(
            "GET",
            "/healthz",
            headers={"Host": f"{config['bind']}:{config['port']}"},
        )
        response = connection.getresponse()
        raw = response.read(MAX_BODY_BYTES + 1)
        if (
            response.status == 200
            and len(raw) <= MAX_BODY_BYTES
            and json.loads(raw.decode("utf-8"))
            == {"ok": True, "interface": "web"}
        ):
            print("Web UI ready")
            return 0
        print(
            f"Web UI readiness check failed with HTTP {response.status}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Web UI readiness check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


def stop(config: dict[str, object]) -> int:
    path = config["pid_file"]
    assert isinstance(path, Path)
    if not path.exists() and not path.is_symlink():
        print(f"Web UI PID file not found: {path}", file=sys.stderr)
        return 1
    try:
        record = read_pid_record(path)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    pid = int(record["pid"])
    if process_start_ticks(pid) != record["startTicks"]:
        print(
            f"Web UI PID file is stale; refusing to signal process {pid}",
            file=sys.stderr,
        )
        return 1
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print("Web UI process is not running", file=sys.stderr)
        return 1
    except PermissionError:
        print("Permission denied stopping Web UI process", file=sys.stderr)
        return 1
    print(f"Sent TERM to Web UI process {pid}")
    return 0


def start(config: dict[str, object], environment: dict[str, str]) -> int:
    if environment.get("TEXT_STATS_WEB_ENABLED") != "1":
        raise ConfigurationError(
            "Web UI is disabled; set TEXT_STATS_WEB_ENABLED=1 to start it"
        )
    try:
        server = BrowserHTTPServer(
            (str(config["bind"]), int(config["port"])), sys.stderr
        )
    except OSError as exc:
        print(f"unable to start Web UI: {exc}", file=sys.stderr)
        return 1

    actual_port = int(server.server_address[1])
    record = pid_record()
    path = config["pid_file"]
    assert isinstance(path, Path)
    stop_event = threading.Event()

    def request_shutdown(_signum, _frame) -> None:
        stop_event.set()

    previous_term = signal.signal(signal.SIGTERM, request_shutdown)
    previous_int = signal.signal(signal.SIGINT, request_shutdown)
    server.timeout = 0.2
    try:
        write_pid_record(path, record)
        print(
            f"text-stats web ready http://{config['bind']}:{actual_port}/",
            file=sys.stderr,
            flush=True,
        )
        while not stop_event.is_set():
            server.handle_request()
        return 0
    finally:
        server.server_close()
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)
        try:
            if read_pid_record(path) == record:
                path.unlink()
        except (ConfigurationError, OSError):
            pass
        print("text-stats web stopped", file=sys.stderr, flush=True)


def parse_arguments(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog="python web/server.py", add_help=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--health", action="store_true")
    group.add_argument("--stop", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        raise ConfigurationError("invalid Web UI command arguments") from exc
    if args.health:
        return "health"
    if args.stop:
        return "stop"
    return "start"


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        action = parse_arguments(arguments)
        config = configuration(dict(os.environ))
        if action == "health":
            return health(config)
        if action == "stop":
            return stop(config)
        return start(config, dict(os.environ))
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return DISABLED_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
