#!/usr/bin/env python3
"""Exercise the MCP Apps 2026-01-26 fixture without Ruby."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".github/fixtures/profiles/mcp-apps-enabled"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"
EXPECTED = sorted([
    "INTERFACES.md", "MCP_APPS.md", "MCP_INTERFACE.md", "RUNTIME.md", "SKILL.md",
    "docs/mcp-transports.md", "mcp/apps/host_bridge.mjs", "mcp/apps/result.html",
    "mcp/server.mjs", "package.json", "src/text_stats.mjs", "tests/test_mcp_apps.mjs",
])
PINS = {
    "@modelcontextprotocol/server": "2.0.0",
    "@modelcontextprotocol/client": "2.0.0",
    "zod": "4.1.13",
}


def environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("RUBYOPT", "PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    return env


def run(command: list[str], *, cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command, cwd=cwd, env=environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(command, 124, stdout, stderr + "command timed out\n")


def init_git(directory: Path) -> None:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        result = run(command, cwd=directory, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {result.stderr}")


def main() -> int:
    failures: list[str] = []
    actual = sorted(
        path.relative_to(FIXTURE).as_posix()
        for path in FIXTURE.rglob("*") if not path.is_dir()
    )
    if actual != EXPECTED:
        failures.append(f"mcp-apps-enabled layout drift: {actual!r}")

    try:
        manifest = json.loads((FIXTURE / "package.json").read_text(encoding="utf-8"))
        dependencies = manifest["dependencies"]
        for package, version in PINS.items():
            if dependencies.get(package) != version:
                failures.append(f"mcp-apps-enabled: expected exact {package}={version} pin")
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        failures.append(f"mcp-apps-enabled package.json: {exc}")

    runtime = (FIXTURE / "RUNTIME.md").read_text(encoding="utf-8")
    if "| Supported protocol revisions | `2026-07-28` |" not in runtime:
        failures.append("mcp-apps-enabled: missing core 2026-07-28 selection")
    if "| Optional MCP extensions | io.modelcontextprotocol/ui |" not in runtime:
        failures.append("mcp-apps-enabled: missing exact Apps extension selection")
    apps = (FIXTURE / "MCP_APPS.md").read_text(encoding="utf-8")
    if "Extension specification revision: 2026-01-26" not in apps:
        failures.append("mcp-apps-enabled: missing Apps 2026-01-26 revision")
    if (FIXTURE / "WEB_INTERFACE.md").exists():
        failures.append("mcp-apps-enabled: must remain independent of browser-interface")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="mcp-apps-profile") as temporary:
        directory = Path(temporary)
        shutil.copytree(FIXTURE, directory, dirs_exist_ok=True, symlinks=True)
        init_git(directory)
        validation = run([sys.executable, str(VALIDATOR), str(directory)], cwd=ROOT, timeout=60)
        if validation.returncode != 0:
            failures.append(
                f"mcp-apps-enabled contract validation failed: stdout={validation.stdout!r}, stderr={validation.stderr!r}"
            )
        install = run(
            ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=directory, timeout=180,
        )
        if install.returncode != 0:
            failures.append(f"mcp-apps-enabled npm install failed: {install.stderr!r}")
        else:
            for script in ("check", "test"):
                result = run(["npm", "run", script], cwd=directory, timeout=120)
                if result.returncode != 0:
                    failures.append(
                        f"mcp-apps-enabled npm run {script} failed: stdout={result.stdout!r}, stderr={result.stderr!r}"
                    )

    with tempfile.TemporaryDirectory(prefix="invalid-mcp-apps-profile") as temporary:
        directory = Path(temporary)
        shutil.copytree(FIXTURE, directory, dirs_exist_ok=True, symlinks=True)
        (directory / "MCP_APPS.md").unlink()
        init_git(directory)
        validation = run([sys.executable, str(VALIDATOR), str(directory)], cwd=ROOT, timeout=60)
        if validation.returncode == 0:
            failures.append("mcp-apps-enabled negative contract: selected Apps without MCP_APPS.md must fail")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("MCP Apps executable fixture tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
