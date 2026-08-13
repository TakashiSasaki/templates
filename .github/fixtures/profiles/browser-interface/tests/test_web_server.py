#!/usr/bin/env python3
"""Executable HTTP/security/lifecycle tests for the browser-interface fixture."""

from __future__ import annotations

import http.client
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "web/server.py"
SECURITY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def base_env(*, port: int, pid_file: Path, enabled: bool = True) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["TEXT_STATS_WEB_BIND"] = "127.0.0.1"
    env["TEXT_STATS_WEB_PORT"] = str(port)
    env["TEXT_STATS_WEB_PID_FILE"] = str(pid_file)
    if enabled:
        env["TEXT_STATS_WEB_ENABLED"] = "1"
    else:
        env.pop("TEXT_STATS_WEB_ENABLED", None)
    return env


def command(
    args: list[str], *, cwd: Path, env: dict[str, str], timeout: float = 3.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SERVER), *args],
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def http_request(
    port: int,
    method: str,
    path: str,
    *,
    host: str | None = None,
    origin: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
    connection.putrequest(method, path, skip_host=True)
    connection.putheader("Host", host or f"127.0.0.1:{port}")
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


def raw_request(port: int, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        sock.sendall(request)
        sock.settimeout(2.0)
        return sock.recv(4096)


def wait_ready(port: int, process: subprocess.Popen, deadline: float = 4.0) -> None:
    end = time.monotonic() + deadline
    last_error: Exception | None = None
    while time.monotonic() < end:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise AssertionError(
                f"server exited before readiness: {process.returncode}; stderr={stderr!r}"
            )
        try:
            status, _, _ = http_request(port, "GET", "/healthz")
            if status == 200:
                return
        except Exception as exc:  # startup race only
            last_error = exc
        time.sleep(0.03)
    raise AssertionError(f"server did not become ready: {last_error}")


def start_server(root: Path) -> tuple[subprocess.Popen, int, Path, dict[str, str]]:
    port = free_port()
    pid_file = root / "web.pid"
    env = base_env(port=port, pid_file=pid_file)
    process = subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    wait_ready(port, process)
    return process, port, pid_file, env


def terminate(process: subprocess.Popen) -> tuple[str, str]:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
    stdout = process.stdout.read() if process.stdout is not None else ""
    stderr = process.stderr.read() if process.stderr is not None else ""
    return stdout, stderr


class BrowserServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="browser-interface-test")
        cls.root = Path(cls.temporary.name)
        cls.process, cls.port, cls.pid_file, cls.env = start_server(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        terminate(cls.process)
        cls.temporary.cleanup()

    def assert_security_headers(self, headers: dict[str, str]) -> None:
        for name, expected in SECURITY_HEADERS.items():
            self.assertEqual(expected, headers.get(name), name)
        self.assertIn("default-src 'none'", headers.get("content-security-policy", ""))
        self.assertNotIn("access-control-allow-origin", headers)

    def test_static_routes_security_and_host_policy(self) -> None:
        for path in ("/", "/app.js", "/app.css", "/healthz"):
            status, headers, body = http_request(self.port, "GET", path)
            self.assertEqual(200, status, path)
            self.assertTrue(body)
            self.assert_security_headers(headers)

        status, _, payload = http_request(self.port, "GET", "/missing")
        self.assertEqual(404, status)
        self.assertFalse(json.loads(payload)["ok"])
        status, headers, _ = http_request(self.port, "POST", "/healthz")
        self.assertEqual(405, status)
        self.assertEqual("GET", headers.get("allow"))
        self.assert_security_headers(headers)
        status, _, _ = http_request(
            self.port, "GET", "/healthz", host=f"example.test:{self.port}"
        )
        self.assertEqual(403, status)
        status, _, _ = http_request(
            self.port, "GET", "/healthz", host=f"127.0.0.1:{self.port}/"
        )
        self.assertEqual(403, status)

    def test_every_method_uses_hardened_dispatch(self) -> None:
        status, headers, _ = http_request(self.port, "OPTIONS", "/healthz")
        self.assertEqual(405, status)
        self.assertEqual("GET", headers.get("allow"))
        self.assert_security_headers(headers)
        status, headers, _ = http_request(
            self.port,
            "PATCH",
            "/healthz",
            host=f"example.test:{self.port}",
        )
        self.assertEqual(403, status)
        self.assert_security_headers(headers)

    def test_same_origin_api_and_redaction(self) -> None:
        body = json.dumps({"text": "one two\n"}).encode()
        status, headers, raw = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            origin=f"http://127.0.0.1:{self.port}",
            body=body,
            content_type="application/json; charset=utf-8",
        )
        self.assertEqual(200, status)
        payload = json.loads(raw)
        self.assertEqual("1", payload["contractVersion"])
        self.assertIs(True, payload["ok"])
        self.assertEqual({"bytes": 8, "lines": 1, "words": 2}, payload["result"])
        self.assertNotIn(b"one two", raw)
        self.assertNotIn("access-control-allow-origin", headers)

        localhost = f"localhost:{self.port}"
        status, _, _ = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            host=localhost,
            origin=f"http://{localhost}",
            body=body,
            content_type="application/json",
        )
        self.assertEqual(200, status)
        status, _, _ = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            host=localhost,
            origin=f"http://127.0.0.1:{self.port}",
            body=body,
            content_type="application/json",
        )
        self.assertEqual(403, status)
        status, _, _ = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            origin=f"http://127.0.0.1:{self.port}/",
            body=body,
            content_type="application/json",
        )
        self.assertEqual(403, status)
        status, _, _ = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            body=body,
            content_type="application/json",
        )
        self.assertEqual(403, status)

    def test_api_validation_failures_leave_health_ready(self) -> None:
        origin = f"http://127.0.0.1:{self.port}"
        cases = [
            (b"{}", "application/json", 422),
            (b'{"text":1}', "application/json", 422),
            (b'{"text":"x","extra":1}', "application/json", 422),
            (b"{", "application/json", 400),
            (b"\xff", "application/json", 400),
            (b'{"text":"x"}', "text/plain", 415),
        ]
        for body, content_type, expected in cases:
            status, _, _ = http_request(
                self.port,
                "POST",
                "/api/text-stats",
                origin=origin,
                body=body,
                content_type=content_type,
            )
            self.assertEqual(expected, status)
            health, _, _ = http_request(self.port, "GET", "/healthz")
            self.assertEqual(200, health)

    def test_body_limits_precede_origin_rejection_and_close_oversize_connections(self) -> None:
        origin = f"http://127.0.0.1:{self.port}"
        too_large = b"x" * (65536 + 1)
        status, headers, _ = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            origin=origin,
            body=too_large,
            content_type="application/json",
        )
        self.assertEqual(413, status)
        self.assertEqual("close", headers.get("connection"))
        status, headers, _ = http_request(
            self.port,
            "POST",
            "/api/text-stats",
            body=too_large,
            content_type="application/json",
        )
        self.assertEqual(413, status)
        self.assertEqual("close", headers.get("connection"))

        request = (
            f"POST /api/text-stats HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            f"Origin: {origin}\r\n"
            "Content-Type: application/json\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Connection: keep-alive\r\n\r\n"
            "10001\r\n"
        ).encode("ascii")
        response = raw_request(self.port, request)
        self.assertIn(b" 413 ", response)
        self.assertIn(b"Connection: close", response)

        negative_chunk = (
            f"POST /api/text-stats HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            f"Origin: {origin}\r\n"
            "Content-Type: application/json\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Connection: close\r\n\r\n"
            "-1\r\n"
        ).encode("ascii")
        response = raw_request(self.port, negative_chunk)
        self.assertIn(b" 400 ", response)

    def test_health_command_and_pid_record(self) -> None:
        result = command(["--health"], cwd=ROOT, env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("Web UI ready\n", result.stdout)
        info = self.pid_file.lstat()
        self.assertTrue(stat.S_ISREG(info.st_mode))
        self.assertFalse(stat.S_ISLNK(info.st_mode))
        self.assertEqual(0o600, stat.S_IMODE(info.st_mode))
        record = json.loads(self.pid_file.read_text(encoding="utf-8"))
        self.assertEqual(self.process.pid, record["pid"])
        self.assertTrue(str(record["startTicks"]).isdigit())


class BrowserLifecycleTests(unittest.TestCase):
    def test_disabled_and_nonloopback_start_fail_promptly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="browser-disabled") as temporary:
            root = Path(temporary)
            env = base_env(port=free_port(), pid_file=root / "pid", enabled=False)
            result = command([], cwd=ROOT, env=env)
            self.assertEqual(78, result.returncode)
            self.assertIn("disabled", result.stderr)
            env = base_env(port=free_port(), pid_file=root / "pid")
            env["TEXT_STATS_WEB_BIND"] = "0.0.0.0"
            result = command([], cwd=ROOT, env=env)
            self.assertEqual(78, result.returncode)
            self.assertIn("127.0.0.1", result.stderr)

    def test_documented_stop_cleans_owned_pid_and_stdout_stays_empty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="browser-stop") as temporary:
            root = Path(temporary)
            process, _, pid_file, env = start_server(root)
            result = command(["--stop"], cwd=ROOT, env=env)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Sent TERM", result.stdout)
            process.wait(timeout=3.0)
            stdout = process.stdout.read() if process.stdout is not None else ""
            stderr = process.stderr.read() if process.stderr is not None else ""
            self.assertEqual(0, process.returncode, stderr)
            self.assertEqual("", stdout)
            self.assertFalse(pid_file.exists())
            self.assertIn("text-stats web stopped", stderr)

    def test_absent_stale_and_symlink_pid_records_never_signal_unrelated_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="browser-stale") as temporary:
            root = Path(temporary)
            pid_file = root / "pid"
            env = base_env(port=free_port(), pid_file=pid_file)
            start = time.monotonic()
            result = command(["--stop"], cwd=ROOT, env=env)
            self.assertLess(time.monotonic() - start, 3.0)
            self.assertNotEqual(0, result.returncode)

            pid_file.write_text(
                json.dumps({"pid": os.getpid(), "startTicks": "1"}) + "\n",
                encoding="utf-8",
            )
            os.chmod(pid_file, 0o600)
            result = command(["--stop"], cwd=ROOT, env=env)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("stale", result.stderr)
            os.kill(os.getpid(), 0)

            pid_file.unlink()
            target = root / "target"
            target.write_text("{}\n", encoding="utf-8")
            pid_file.symlink_to(target.name)
            result = command(["--stop"], cwd=ROOT, env=env)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("non-symlink", result.stderr)

    def test_preexisting_pid_and_live_port_collision_fail_without_hanging(self) -> None:
        with tempfile.TemporaryDirectory(prefix="browser-collision") as temporary:
            root = Path(temporary)
            process, port, _, env = start_server(root)
            try:
                other_pid = root / "other.pid"
                collision_env = base_env(port=port, pid_file=other_pid)
                result = command([], cwd=ROOT, env=collision_env)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("unable to start", result.stderr)
                self.assertFalse(other_pid.exists())

                occupied_pid = root / "occupied.pid"
                occupied_pid.write_text("sentinel\n", encoding="utf-8")
                occupied_env = base_env(port=free_port(), pid_file=occupied_pid)
                result = command([], cwd=ROOT, env=occupied_env)
                self.assertEqual(78, result.returncode)
                self.assertIn("already exists", result.stderr)
                self.assertEqual("sentinel\n", occupied_pid.read_text(encoding="utf-8"))
            finally:
                terminate(process)


if __name__ == "__main__":
    unittest.main(verbosity=2)
