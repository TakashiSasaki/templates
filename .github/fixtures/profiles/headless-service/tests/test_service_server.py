#!/usr/bin/env python3
"""Executable security, HTTP, concurrency, health, and lifecycle tests."""

from __future__ import annotations

import http.client
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "service/server.py"
TOKEN = "test-token-0123456789-abcdefghijklmnopqrstuvwxyz"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def make_token(path: Path, value: str = TOKEN, mode: int = 0o600) -> None:
    path.write_text(value + "\n", encoding="ascii")
    os.chmod(path, mode)


def base_env(
    *, port: int, pid_file: Path, token_file: Path | None
) -> dict[str, str]:
    env = {
        "TEXT_STATS_SERVICE_PORT": str(port),
        "TEXT_STATS_SERVICE_PID_FILE": str(pid_file),
    }
    if token_file is not None:
        env["TEXT_STATS_SERVICE_TOKEN_FILE"] = str(token_file)
    return env


def command(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path = ROOT,
    timeout: float = 6.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SERVER), *args],
        cwd=cwd,
        env=clean_env(env),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def request(
    port: int,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    token: str | None = TOKEN,
    host: str | None = None,
    origin: str | None = None,
    content_type: str | None = "application/json",
    timeout: float = 4.0,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    connection.putrequest(method, path, skip_host=True)
    connection.putheader("Host", host or f"127.0.0.1:{port}")
    if token is not None:
        connection.putheader("Authorization", f"Bearer {token}")
    if origin is not None:
        connection.putheader("Origin", origin)
    if content_type is not None:
        connection.putheader("Content-Type", content_type)
    if body is not None:
        connection.putheader("Content-Length", str(len(body)))
    connection.endheaders(body)
    response = connection.getresponse()
    raw = response.read()
    headers = {name.lower(): value for name, value in response.getheaders()}
    status = response.status
    connection.close()
    return status, headers, raw


class RunningService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.port = free_port()
        self.pid_file = root / "service.pid"
        self.token_file = root / "token"
        self.stdout_file = root / "stdout.log"
        self.stderr_file = root / "stderr.log"
        make_token(self.token_file)
        self.env = base_env(
            port=self.port,
            pid_file=self.pid_file,
            token_file=self.token_file,
        )
        self.stdout_handle = self.stdout_file.open("wb")
        self.stderr_handle = self.stderr_file.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=ROOT,
            env=clean_env(self.env),
            stdin=subprocess.DEVNULL,
            stdout=self.stdout_handle,
            stderr=self.stderr_handle,
        )
        self._wait_ready()

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + 8.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.stderr_handle.flush()
                raise AssertionError(
                    f"service exited before readiness: {self.process.returncode}; "
                    f"stderr={self.stderr_file.read_text(encoding='utf-8', errors='replace')!r}"
                )
            try:
                status, _, _ = request(
                    self.port,
                    "GET",
                    "/livez",
                    token=None,
                    content_type=None,
                    timeout=0.4,
                )
                if status == 200 and self.pid_file.is_file():
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(0.03)
        raise AssertionError(f"service did not become ready: {last_error}")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=4.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2.0)
        self.stdout_handle.close()
        self.stderr_handle.close()


class ServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="headless-service-test")
        self.root = Path(self.temporary.name)
        self.service = RunningService(self.root)

    def tearDown(self) -> None:
        self.service.close()
        self.temporary.cleanup()

    def test_http_contract_authentication_and_non_browser_boundary(self) -> None:
        port = self.service.port
        status, _, raw = request(port, "GET", "/livez", token=None, content_type=None)
        self.assertEqual(200, status)
        self.assertEqual({"ok": True, "status": "live"}, json.loads(raw))
        status, _, raw = request(port, "GET", "/readyz", token=None, content_type=None)
        self.assertEqual(200, status)
        self.assertEqual({"ok": True, "status": "ready"}, json.loads(raw))

        body = json.dumps({"text": "alpha beta\n"}).encode()
        status, headers, raw = request(port, "POST", "/v1/text-stats", body=body)
        self.assertEqual(200, status)
        self.assertEqual(
            {
                "contractVersion": 1,
                "ok": True,
                "result": {"bytes": 11, "lines": 1, "words": 2},
            },
            json.loads(raw),
        )
        self.assertNotIn(b"alpha", raw)
        self.assertEqual("no-store", headers.get("cache-control"))
        self.assertEqual("nosniff", headers.get("x-content-type-options"))
        self.assertEqual("DENY", headers.get("x-frame-options"))
        self.assertNotIn("access-control-allow-origin", headers)

        status, headers, _ = request(
            port, "POST", "/v1/text-stats", body=body, token=None
        )
        self.assertEqual(401, status)
        self.assertEqual('Bearer realm="text-stats-service"', headers.get("www-authenticate"))
        self.assertEqual(
            401,
            request(port, "POST", "/v1/text-stats", body=body, token="x" * 40)[0],
        )
        self.assertEqual(
            403,
            request(
                port,
                "POST",
                "/v1/text-stats",
                body=body,
                origin=f"http://127.0.0.1:{port}",
            )[0],
        )
        self.assertEqual(
            403,
            request(
                port,
                "GET",
                "/livez",
                token=None,
                content_type=None,
                origin=f"http://127.0.0.1:{port}",
            )[0],
        )
        self.assertEqual(
            403,
            request(
                port,
                "GET",
                "/livez",
                token=None,
                content_type=None,
                host="example.test",
            )[0],
        )
        status, headers, _ = request(
            port, "GET", "/v1/text-stats", token=None, content_type=None
        )
        self.assertEqual(405, status)
        self.assertEqual("POST", headers.get("allow"))
        self.assertEqual(
            404,
            request(port, "GET", "/missing", token=None, content_type=None)[0],
        )

        self.service.stderr_handle.flush()
        diagnostics = self.service.stderr_file.read_text(
            encoding="utf-8", errors="replace"
        )
        self.assertNotIn(TOKEN, diagnostics)
        self.assertNotIn("alpha beta", diagnostics)

    def test_validation_size_limits_and_health_isolation(self) -> None:
        port = self.service.port
        origin = None
        self.assertEqual(
            415,
            request(
                port,
                "POST",
                "/v1/text-stats",
                body=b"{}",
                content_type="text/plain",
            )[0],
        )
        self.assertEqual(
            400,
            request(port, "POST", "/v1/text-stats", body=b"\xff")[0],
        )
        self.assertEqual(
            400,
            request(port, "POST", "/v1/text-stats", body=b"{")[0],
        )
        self.assertEqual(
            422,
            request(
                port,
                "POST",
                "/v1/text-stats",
                body=json.dumps({"text": "x", "extra": True}).encode(),
            )[0],
        )
        status, headers, _ = request(
            port, "POST", "/v1/text-stats", body=b"x" * 65537
        )
        self.assertEqual(413, status)
        self.assertEqual("close", headers.get("connection", "").lower())

        with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
            sock.sendall(
                (
                    f"POST /v1/text-stats HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\n"
                    f"Authorization: Bearer {TOKEN}\r\n"
                    "Content-Type: application/json\r\n"
                    "Transfer-Encoding: chunked\r\n\r\n"
                    "10000\r\n"
                ).encode("ascii")
                + b"x" * 65536
                + b"\r\n1\r\nx\r\n0\r\n\r\n"
            )
            response = bytearray()
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
        self.assertIn(b" 413 ", response)
        self.assertIn(b"Connection: close", response)
        self.assertEqual(
            200,
            request(port, "GET", "/readyz", token=None, content_type=None)[0],
        )
        self.assertEqual(
            200,
            request(port, "GET", "/livez", token=None, content_type=None)[0],
        )

    def test_stalled_body_gets_408_releases_api_slot_and_keeps_health_available(self) -> None:
        port = self.service.port
        first = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        first.settimeout(5.0)
        first.sendall(
            (
                f"POST /v1/text-stats HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                f"Authorization: Bearer {TOKEN}\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: 20\r\n\r\n{"
            ).encode("ascii")
        )
        time.sleep(0.15)

        status, _, raw = request(
            port,
            "POST",
            "/v1/text-stats",
            body=json.dumps({"text": "second"}).encode(),
        )
        self.assertEqual(503, status)
        self.assertEqual("service is busy or draining", json.loads(raw)["error"])
        self.assertEqual(
            200,
            request(port, "GET", "/readyz", token=None, content_type=None)[0],
        )
        self.assertEqual(
            200,
            request(port, "GET", "/livez", token=None, content_type=None)[0],
        )

        response = bytearray()
        while True:
            chunk = first.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
        first.close()
        self.assertIn(b" 408 ", response)
        self.assertIn(b"Connection: close", response)
        self.assertIn(b'"error":"request timed out"', response)

        status, _, _ = request(
            port,
            "POST",
            "/v1/text-stats",
            body=json.dumps({"text": "after timeout"}).encode(),
        )
        self.assertEqual(200, status)

    def test_health_commands_and_identity_verified_shutdown(self) -> None:
        env = self.service.env
        ready = command(["--health"], env=env)
        self.assertEqual(0, ready.returncode, ready.stderr)
        self.assertEqual("Headless service ready\n", ready.stdout)
        live = command(["--live"], env=env)
        self.assertEqual(0, live.returncode, live.stderr)
        self.assertEqual("Headless service live\n", live.stdout)

        info = self.service.pid_file.lstat()
        self.assertEqual(0o600, stat.S_IMODE(info.st_mode))
        record = json.loads(self.service.pid_file.read_text(encoding="utf-8"))
        self.assertEqual(self.service.process.pid, record["pid"])
        self.assertTrue(record["startTicks"].isdigit())

        stopped = command(["--stop"], env=env)
        self.assertEqual(0, stopped.returncode, stopped.stderr)
        self.assertIn("Sent TERM", stopped.stdout)
        self.service.process.wait(timeout=4.0)
        self.assertEqual(0, self.service.process.returncode)
        self.assertFalse(self.service.pid_file.exists())
        self.service.stdout_handle.flush()
        self.service.stderr_handle.flush()
        self.assertEqual(b"", self.service.stdout_file.read_bytes())
        self.assertIn(
            "text-stats service stopped",
            self.service.stderr_file.read_text(encoding="utf-8", errors="replace"),
        )


class ConfigurationAndProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="headless-config-test")
        self.root = Path(self.temporary.name)
        self.token = self.root / "token"
        self.pid = self.root / "service.pid"
        make_token(self.token)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def env(self, *, port: int = 0, token_file: Path | None = None) -> dict[str, str]:
        return base_env(
            port=port,
            pid_file=self.pid,
            token_file=self.token if token_file is None else token_file,
        )

    def test_configuration_token_and_fifo_guards(self) -> None:
        missing = command(
            [],
            env=base_env(port=0, pid_file=self.pid, token_file=None),
        )
        self.assertEqual(78, missing.returncode)
        self.assertIn("TEXT_STATS_SERVICE_TOKEN_FILE is required", missing.stderr)

        nonloop = self.env()
        nonloop["TEXT_STATS_SERVICE_BIND"] = "0.0.0.0"
        result = command([], env=nonloop)
        self.assertEqual(78, result.returncode)
        self.assertIn("127.0.0.1", result.stderr)

        os.chmod(self.token, 0o644)
        result = command([], env=self.env())
        self.assertEqual(78, result.returncode)
        self.assertIn("group or other", result.stderr)
        os.chmod(self.token, 0o600)

        target = self.root / "token-target"
        make_token(target)
        link = self.root / "token-link"
        link.symlink_to(target.name)
        result = command([], env=self.env(token_file=link))
        self.assertEqual(78, result.returncode)
        self.assertIn("regular non-symlink", result.stderr)

        fifo = self.root / "token-fifo"
        os.mkfifo(fifo, 0o600)
        started = time.monotonic()
        result = command([], env=self.env(token_file=fifo), timeout=3.0)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(78, result.returncode)
        self.assertIn("regular non-symlink", result.stderr)

    def test_stale_preexisting_symlink_and_fifo_pid_records_do_not_signal(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        from text_stats import process_start_ticks  # noqa: PLC0415

        ticks = process_start_ticks(os.getpid())
        self.assertIsNotNone(ticks)
        self.pid.write_text(
            json.dumps(
                {"pid": os.getpid(), "startTicks": str(int(ticks) + 1)}
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(self.pid, 0o600)
        result = command(["--stop"], env=self.env(port=4568))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("stale; refusing to signal", result.stderr)
        os.kill(os.getpid(), 0)

        self.pid.write_text("existing\n", encoding="utf-8")
        os.chmod(self.pid, 0o600)
        result = command([], env=self.env())
        self.assertEqual(78, result.returncode)
        self.assertIn("PID file already exists", result.stderr)

        self.pid.unlink()
        target = self.root / "pid-target"
        target.write_text("target\n", encoding="utf-8")
        self.pid.symlink_to(target.name)
        result = command([], env=self.env())
        self.assertEqual(78, result.returncode)
        self.assertIn("PID file already exists", result.stderr)
        self.assertEqual("target\n", target.read_text(encoding="utf-8"))

        self.pid.unlink()
        os.mkfifo(self.pid, 0o600)
        started = time.monotonic()
        result = command(["--stop"], env=self.env(port=4568), timeout=3.0)
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("regular non-symlink", result.stderr)

    def test_fixed_port_collision_fails_promptly(self) -> None:
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        try:
            port = blocker.getsockname()[1]
            result = command([], env=self.env(port=port), timeout=4.0)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("unable to start headless service", result.stderr)
        finally:
            blocker.close()

    def test_health_probe_deadline_and_body_cap(self) -> None:
        def serve_streaming(server: socket.socket) -> None:
            connection, _ = server.accept()
            with connection:
                data = bytearray()
                while b"\r\n\r\n" not in data:
                    data.extend(connection.recv(1024))
                connection.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    b"Transfer-Encoding: chunked\r\n\r\n"
                )
                try:
                    while True:
                        connection.sendall(b"1\r\nx\r\n")
                        time.sleep(0.05)
                except OSError:
                    pass

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        thread = threading.Thread(target=serve_streaming, args=(server,), daemon=True)
        thread.start()
        port = server.getsockname()[1]
        started = time.monotonic()
        result = command(["--health"], env=self.env(port=port), timeout=5.0)
        elapsed = time.monotonic() - started
        server.close()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("overall deadline exceeded", result.stderr)
        self.assertLess(elapsed, 4.0)

        def serve_oversized(server_socket: socket.socket) -> None:
            connection, _ = server_socket.accept()
            with connection:
                data = bytearray()
                while b"\r\n\r\n" not in data:
                    data.extend(connection.recv(1024))
                body = b"x" * 5000
                connection.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\n".encode("ascii")
                    + b"Connection: close\r\n\r\n"
                    + body
                )

        oversized = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        oversized.bind(("127.0.0.1", 0))
        oversized.listen(1)
        thread = threading.Thread(target=serve_oversized, args=(oversized,), daemon=True)
        thread.start()
        result = command(
            ["--live"], env=self.env(port=oversized.getsockname()[1]), timeout=5.0
        )
        oversized.close()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("health response exceeds 4096 bytes", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
