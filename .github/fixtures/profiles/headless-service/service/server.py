#!/usr/bin/env python3
"""Authenticated loopback-only headless text-statistics service."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import signal
import socket
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from text_stats import (  # noqa: E402
    CONTRACT_VERSION,
    ConfigurationError,
    analyze,
    current_pid_record,
    process_start_ticks,
    read_bounded_health_response,
    read_pid_record,
    read_token,
    write_pid_record,
)

DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 4568
DEFAULT_PID_FILE = "tmp/text-stats-service.pid"
CONFIGURATION_EXIT = 78
MAX_BODY_BYTES = 64 * 1024
MAX_CLIENT_THREADS = 8
MAX_CONCURRENT_API_REQUESTS = 1
REQUEST_TIMEOUT_SECONDS = 2.0
KEEP_ALIVE_TIMEOUT_SECONDS = 1.0
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
KNOWN_PATHS = {"/livez", "/readyz", "/v1/text-stats"}
BEARER = re.compile(r"Bearer ([!-~]{1,512})\Z")


class RequestError(RuntimeError):
    def __init__(
        self,
        status: int,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        close_connection: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.headers = headers or {}
        self.close_connection = close_connection


class ServiceState:
    def __init__(self, token: str) -> None:
        self.token_digest = hashlib.sha256(token.encode("ascii")).digest()
        self._lock = threading.Lock()
        self._active_api_requests = 0
        self._ready = True

    def mark_draining(self) -> None:
        with self._lock:
            self._ready = False

    def ready(self) -> bool:
        with self._lock:
            return self._ready

    def acquire_api_slot(self) -> bool:
        with self._lock:
            if (
                not self._ready
                or self._active_api_requests >= MAX_CONCURRENT_API_REQUESTS
            ):
                return False
            self._active_api_requests += 1
            return True

    def release_api_slot(self) -> None:
        with self._lock:
            self._active_api_requests -= 1


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True
    allow_reuse_address = True
    request_queue_size = MAX_CLIENT_THREADS

    def __init__(
        self,
        address: tuple[str, int],
        *,
        state: ServiceState,
        diagnostic,
    ) -> None:
        self.state = state
        self.diagnostic = diagnostic
        self._client_slots = threading.BoundedSemaphore(MAX_CLIENT_THREADS)
        super().__init__(address, ServiceHandler)

    def process_request(self, request, client_address) -> None:
        self._client_slots.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self._client_slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._client_slots.release()


class ServiceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TextStatsService/1"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(KEEP_ALIVE_TIMEOUT_SECONDS)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    @property
    def state(self) -> ServiceState:
        return self.server.state  # type: ignore[attr-defined]

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

    def _service(self, method: str) -> None:
        status = 500
        api_slot = False
        try:
            self._authorize_host()
            self._reject_browser_origin()
            if method == "GET" and self.path == "/livez":
                status = 200
                self._respond_json(status, {"ok": True, "status": "live"})
            elif method == "GET" and self.path == "/readyz":
                ready = self.state.ready()
                status = 200 if ready else 503
                self._respond_json(
                    status,
                    {
                        "ok": ready,
                        "status": "ready" if ready else "draining",
                    },
                )
            elif method == "POST" and self.path == "/v1/text-stats":
                api_slot = self.state.acquire_api_slot()
                if not api_slot:
                    raise RequestError(
                        503,
                        "service is busy or draining",
                        close_connection=True,
                    )
                self._authorize_bearer()
                status, payload = self._handle_stats()
                self._respond_json(status, payload)
            elif self.path in KNOWN_PATHS:
                status = 405
                allow = "POST" if self.path == "/v1/text-stats" else "GET"
                self._respond_json(
                    status,
                    {"ok": False, "error": "method not allowed"},
                    extra_headers={"Allow": allow},
                )
            else:
                status = 404
                self._respond_json(status, {"ok": False, "error": "not found"})
        except socket.timeout:
            status = 408
            self.close_connection = True
            self._respond_json(
                status,
                {"ok": False, "error": "request timed out"},
                extra_headers={"Connection": "close"},
            )
        except RequestError as exc:
            status = exc.status
            if exc.close_connection:
                self.close_connection = True
            headers = dict(exc.headers)
            if exc.close_connection:
                headers["Connection"] = "close"
            self._respond_json(
                status,
                {"ok": False, "error": str(exc)},
                extra_headers=headers,
            )
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            status = 500
            self.close_connection = True
            print(
                f"service request failed: {type(exc).__name__}: {exc}",
                file=self.diagnostic,
                flush=True,
            )
            try:
                self._respond_json(
                    status,
                    {"ok": False, "error": "internal server error"},
                    extra_headers={"Connection": "close"},
                )
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            if api_slot:
                self.state.release_api_slot()
            self.connection.settimeout(KEEP_ALIVE_TIMEOUT_SECONDS)
            print(
                f"service request {method} {self.path} -> {status}",
                file=self.diagnostic,
                flush=True,
            )

    def _authorize_host(self) -> None:
        host = self.headers.get("Host", "").lower()
        allowed = {f"127.0.0.1:{self.active_port}", f"localhost:{self.active_port}"}
        if self.active_port == 80:
            allowed.update({"127.0.0.1", "localhost"})
        if host not in allowed:
            raise RequestError(403, "forbidden host", close_connection=True)

    def _reject_browser_origin(self) -> None:
        if self.headers.get("Origin", ""):
            raise RequestError(
                403,
                "browser-origin requests are not supported",
                close_connection=True,
            )

    def _authorize_bearer(self) -> None:
        authorization = self.headers.get("Authorization", "")
        match = BEARER.fullmatch(authorization)
        supplied_digest = (
            hashlib.sha256(match.group(1).encode("ascii")).digest()
            if match is not None
            else None
        )
        if supplied_digest is None or not hmac.compare_digest(
            supplied_digest, self.state.token_digest
        ):
            raise RequestError(
                401,
                "valid bearer token required",
                headers={"WWW-Authenticate": 'Bearer realm="text-stats-service"'},
                close_connection=True,
            )

    def _handle_stats(self) -> tuple[int, dict[str, object]]:
        media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise RequestError(
                415,
                "application/json is required",
                close_connection=True,
            )
        self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        raw = self._read_bounded_body()
        try:
            text = raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise RequestError(
                400,
                "request body is not valid UTF-8",
                close_connection=True,
            ) from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RequestError(
                400,
                "invalid JSON request body",
                close_connection=True,
            ) from exc
        if (
            type(payload) is not dict
            or list(payload.keys()) != ["text"]
            or type(payload.get("text")) is not str
        ):
            raise RequestError(
                422,
                "request must contain only one string field named text",
                close_connection=True,
            )
        return (
            200,
            {
                "contractVersion": CONTRACT_VERSION,
                "ok": True,
                "result": analyze(payload["text"]),
            },
        )

    def _read_bounded_body(self) -> bytes:
        transfer_encoding = self.headers.get("Transfer-Encoding", "").strip().lower()
        if transfer_encoding:
            if transfer_encoding != "chunked":
                raise RequestError(
                    400,
                    "unsupported transfer encoding",
                    close_connection=True,
                )
            return self._read_chunked_body()

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            return b""
        if not content_length.isascii() or not content_length.isdigit():
            raise RequestError(400, "invalid Content-Length", close_connection=True)
        length = int(content_length, 10)
        if length > MAX_BODY_BYTES:
            raise RequestError(
                413,
                "request body exceeds 65536 bytes",
                close_connection=True,
            )
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestError(400, "incomplete request body", close_connection=True)
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
        self.send_response(status)
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()


def configuration(environment: dict[str, str]) -> dict[str, object]:
    bind = environment.get("TEXT_STATS_SERVICE_BIND", DEFAULT_BIND)
    if bind != DEFAULT_BIND:
        raise ConfigurationError("TEXT_STATS_SERVICE_BIND must be 127.0.0.1")
    raw_port = environment.get("TEXT_STATS_SERVICE_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port, 10)
    except ValueError as exc:
        raise ConfigurationError(
            "TEXT_STATS_SERVICE_PORT must be an integer between 0 and 65535"
        ) from exc
    if not 0 <= port <= 65535:
        raise ConfigurationError("TEXT_STATS_SERVICE_PORT must be between 0 and 65535")
    raw_pid = environment.get("TEXT_STATS_SERVICE_PID_FILE", DEFAULT_PID_FILE)
    raw_token = environment.get("TEXT_STATS_SERVICE_TOKEN_FILE")
    return {
        "bind": bind,
        "port": port,
        "pid_file": Path(os.path.abspath(raw_pid)),
        "token_file": Path(os.path.abspath(raw_token)) if raw_token else None,
    }


def health(config: dict[str, object], path: str, expected: str) -> int:
    try:
        status, body = read_bounded_health_response(
            str(config["bind"]), int(config["port"]), path
        )
        payload = json.loads(body.decode("utf-8"))
        if status == "200" and payload == {"ok": True, "status": expected}:
            print(f"Headless service {expected}")
            return 0
        print(
            f"Headless service {expected} check failed with HTTP {status}",
            file=sys.stderr,
        )
        return 1
    except TimeoutError:
        print(
            f"Headless service {expected} check failed: overall deadline exceeded",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"Headless service {expected} check failed: {exc}",
            file=sys.stderr,
        )
        return 1


def stop(config: dict[str, object]) -> int:
    path = config["pid_file"]
    assert isinstance(path, Path)
    if not path.exists() and not path.is_symlink():
        print(f"Headless service PID file not found: {path}", file=sys.stderr)
        return 1
    try:
        record = read_pid_record(path)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    pid = int(record["pid"])
    if process_start_ticks(pid) != record["startTicks"]:
        print(
            f"Headless service PID file is stale; refusing to signal process {pid}",
            file=sys.stderr,
        )
        return 1
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print("Headless service process is not running", file=sys.stderr)
        return 1
    except PermissionError:
        print("Permission denied stopping headless service process", file=sys.stderr)
        return 1
    print(f"Sent TERM to headless service process {pid}")
    return 0


def start(config: dict[str, object]) -> int:
    token_path = config["token_file"]
    assert token_path is None or isinstance(token_path, Path)
    token = read_token(token_path)
    state = ServiceState(token)
    try:
        server = BoundedThreadingHTTPServer(
            (str(config["bind"]), int(config["port"])),
            state=state,
            diagnostic=sys.stderr,
        )
    except OSError as exc:
        print(f"unable to start headless service: {exc}", file=sys.stderr)
        return 1

    actual_port = int(server.server_address[1])
    pid_file = config["pid_file"]
    assert isinstance(pid_file, Path)
    record = current_pid_record()
    stop_event = threading.Event()

    def request_shutdown(_signum, _frame) -> None:
        state.mark_draining()
        stop_event.set()

    previous_term = signal.signal(signal.SIGTERM, request_shutdown)
    previous_int = signal.signal(signal.SIGINT, request_shutdown)
    server.timeout = 0.2
    try:
        write_pid_record(pid_file, record)
        print(
            f"text-stats service ready http://{config['bind']}:{actual_port}/",
            file=sys.stderr,
            flush=True,
        )
        while not stop_event.is_set():
            server.handle_request()
        return 0
    finally:
        state.mark_draining()
        server.server_close()
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)
        try:
            if read_pid_record(pid_file) == record:
                pid_file.unlink()
        except (ConfigurationError, OSError):
            pass
        print("text-stats service stopped", file=sys.stderr, flush=True)


def parse_arguments(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog="python service/server.py")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--health", action="store_true")
    group.add_argument("--live", action="store_true")
    group.add_argument("--stop", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        raise ConfigurationError("invalid headless service command arguments") from exc
    if args.health:
        return "health"
    if args.live:
        return "live"
    if args.stop:
        return "stop"
    return "start"


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        action = parse_arguments(arguments)
        config = configuration(dict(os.environ))
        if action == "health":
            return health(config, "/readyz", "ready")
        if action == "live":
            return health(config, "/livez", "live")
        if action == "stop":
            return stop(config)
        return start(config)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return CONFIGURATION_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
