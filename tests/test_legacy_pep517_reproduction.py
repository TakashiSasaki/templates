"""Reproduce index-selected PEP 517 backend execution with controlled inputs."""

from __future__ import annotations

import base64
import hashlib
import http.server
import os
import socketserver
import subprocess
import sys
import threading
import zipfile
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTED_TOOLCHAIN = "aa6f9ac4822cbbb9b7bb6940525d54ad690d76d3"
BACKEND_WHEEL = "hatchling-1.31.0-py3-none-any.whl"


def _backend_wheel(path: Path) -> None:
    build = b"""from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


def get_requires_for_build_wheel(config_settings=None):
    Path(os.environ['PIP_TEST_BACKEND_MARKER']).write_text(
        'isolated PEP 517 hook executed\\n', encoding='utf-8'
    )
    return []


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    Path(os.environ['PIP_TEST_BACKEND_MARKER']).write_text(
        'index-selected Hatchling-compatible backend executed\\n', encoding='utf-8'
    )
    filename = 'takashisasaki_agent_policy-0.1.0-py3-none-any.whl'
    dist_info = 'takashisasaki_agent_policy-0.1.0.dist-info'
    entries = {
        f'{dist_info}/METADATA': (
            b'Metadata-Version: 2.1\\n'
            b'Name: takashisasaki-agent-policy\\n'
            b'Version: 0.1.0\\n\\n'
        ),
        f'{dist_info}/WHEEL': (
            b'Wheel-Version: 1.0\\n'
            b'Generator: controlled-reproduction\\n'
            b'Root-Is-Purelib: true\\n'
            b'Tag: py3-none-any\\n'
        ),
    }
    rows = []
    for name, payload in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip('=')
        rows.append(f'{name},sha256={digest},{len(payload)}')
    rows.append(f'{dist_info}/RECORD,,')
    entries[f'{dist_info}/RECORD'] = ('\\n'.join(rows) + '\\n').encode()
    with ZipFile(Path(wheel_directory) / filename, 'w', compression=ZIP_STORED) as wheel:
        for name, payload in entries.items():
            wheel.writestr(name, payload)
    return filename
"""
    metadata = (
        b"Metadata-Version: 2.1\n"
        b"Name: hatchling\n"
        b"Version: 1.31.0\n\n"
    )
    wheel_metadata = (
        b"Wheel-Version: 1.0\n"
        b"Generator: controlled-reproduction\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )
    entries = {
        "hatchling/__init__.py": b"__version__ = '1.31.0'\n",
        "hatchling/build.py": build,
        "hatchling-1.31.0.dist-info/METADATA": metadata,
        "hatchling-1.31.0.dist-info/WHEEL": wheel_metadata,
    }
    record_rows = []
    for name, payload in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip("=")
        record_rows.append(f"{name},sha256={digest},{len(payload)}")
    record_rows.append("hatchling-1.31.0.dist-info/RECORD,,")
    entries["hatchling-1.31.0.dist-info/RECORD"] = (
        "\n".join(record_rows) + "\n"
    ).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as wheel:
        for name, payload in entries.items():
            wheel.writestr(name, payload)


def test_legacy_git_install_resolves_and_executes_index_backend_before_freeze(
    tmp_path: Path,
) -> None:
    common_dir = Path(
        subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ).resolve()
    mirror = tmp_path / "templates.git"
    subprocess.run(
        ["git", "clone", "--bare", "--shared", str(common_dir), str(mirror)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "--no-replace-objects", "-C", str(mirror), "cat-file", "-e", SELECTED_TOOLCHAIN],
        check=True,
        capture_output=True,
        text=True,
    )

    index = tmp_path / "index"
    simple = index / "simple/hatchling"
    packages = index / "packages"
    simple.mkdir(parents=True)
    packages.mkdir()
    _backend_wheel(packages / BACKEND_WHEEL)
    (simple / "index.html").write_text(
        f'<a href="/packages/{BACKEND_WHEEL}">{BACKEND_WHEEL}</a>\n',
        encoding="utf-8",
    )
    requests: list[str] = []

    class RecordingHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append(self.path)
            super().do_GET()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    handler = partial(RecordingHandler, directory=str(index))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            venv = tmp_path / "runtime-venv"
            subprocess.run(
                [sys.executable, "-I", "-m", "venv", str(venv)],
                check=True,
                capture_output=True,
                text=True,
            )
            python = venv / "bin/python"
            marker = tmp_path / "backend-executed.txt"
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.upper().startswith("PIP_")
                and not key.upper().startswith("PYTHON")
                and key not in {"GITHUB_TOKEN", "GH_TOKEN"}
            }
            env.update(
                {
                    "HOME": str(tmp_path / "home"),
                    "PIP_CONFIG_FILE": os.devnull,
                    "PIP_INDEX_URL": f"http://127.0.0.1:{server.server_address[1]}/simple/",
                    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                    "PIP_TEST_BACKEND_MARKER": str(marker),
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": f"url.file://{mirror}.insteadOf",
                    "GIT_CONFIG_VALUE_0": "https://github.com/TakashiSasaki/templates.git",
                }
            )
            command = [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-deps",
                f"git+https://github.com/TakashiSasaki/templates.git@{SELECTED_TOOLCHAIN}",
            ]
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=90,
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text(encoding="utf-8") == (
        "index-selected Hatchling-compatible backend executed\n"
    )
    assert any(path.startswith("/simple/hatchling/") for path in requests)
    assert any(path.endswith(f"/packages/{BACKEND_WHEEL}") for path in requests)
    runtime_lock = (ROOT / "requirements-runtime.lock").read_text(encoding="utf-8")
    assert "hatchling" not in runtime_lock.lower()
    assert "--no-build-isolation" not in command
    assert "--no-index" not in command
