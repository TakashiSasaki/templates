#!/usr/bin/env python3
"""Python-only mutation regressions for canonical profile/interface validators."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / ".github/fixtures/profiles"
VALIDATOR = ROOT / "template/.github/scripts/validate_skill_repository.py"


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "RUBYOPT"):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, env=clean_env(), text=True, encoding="utf-8",
        capture_output=True, check=False,
    )


def initialize_git(directory: Path) -> None:
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        result = run(command, cwd=directory)
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {result.stderr}")


def validate(directory: Path) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(VALIDATOR), str(directory)], cwd=ROOT)


def replace_required(path: Path, before: str, after: str) -> None:
    text = path.read_text(encoding="utf-8")
    if before not in text:
        raise RuntimeError(f"required mutation source is missing in {path}: {before!r}")
    path.write_text(text.replace(before, after, 1), encoding="utf-8")


def remove_heading_section(path: Path, heading: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration as exc:
        raise RuntimeError(f"heading is missing in {path}: {heading}") from exc
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].lstrip()
        if not stripped.startswith("#"):
            continue
        candidate_level = len(stripped) - len(stripped.lstrip("#"))
        if candidate_level <= level:
            end = index
            break
    path.write_text("".join(lines[:start] + lines[end:]), encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    positive_fixtures = [
        "instruction-only",
        "script-assisted",
        "packaged-cli",
        "mcp-enabled",
        "mcp-apps-enabled",
        "browser-interface",
        "headless-service",
    ]
    for fixture_name in positive_fixtures:
        with tempfile.TemporaryDirectory(prefix=f"positive-{fixture_name}") as temporary:
            directory = Path(temporary)
            shutil.copytree(FIXTURES / fixture_name, directory, dirs_exist_ok=True, symlinks=True)
            initialize_git(directory)
            result = validate(directory)
            if result.returncode != 0:
                failures.append(
                    f"{fixture_name}: canonical repository validation failed; stderr={result.stderr!r}"
                )

    cases: list[tuple[str, str, Callable[[Path], None], str | None]] = [
        (
            "instruction-only rejects an unrelated CLI contract",
            "instruction-only",
            lambda directory: (directory / "CLI_INTERFACE.md").write_text(
                "# Unsupported CLI contract\n", encoding="utf-8"
            ),
            None,
        ),
        (
            "packaged CLI requires its caller contract",
            "packaged-cli",
            lambda directory: (directory / "CLI_INTERFACE.md").unlink(),
            None,
        ),
        (
            "packaged CLI rejects an out-of-range exit code",
            "packaged-cli",
            lambda directory: replace_required(
                directory / "CLI_INTERFACE.md",
                "| 5 | Output or diagnostics could not be written or flushed because of an I/O failure |",
                "| 256 | Output or diagnostics could not be written or flushed because of an I/O failure |",
            ),
            None,
        ),
        (
            "packaged CLI rejects runtime command drift",
            "packaged-cli",
            lambda directory: replace_required(
                directory / "RUNTIME.md", "| Human CLI | `text-stat` |", "| Human CLI | `other-stat` |"
            ),
            None,
        ),
        (
            "packaged CLI rejects an unresolved selected scalar",
            "packaged-cli",
            lambda directory: replace_required(
                directory / "RUNTIME.md", "| Runtime | CPython |", "| Runtime | TBD |"
            ),
            "placeholder",
        ),
        (
            "MCP requires MCP_INTERFACE.md",
            "mcp-enabled",
            lambda directory: (directory / "MCP_INTERFACE.md").unlink(),
            None,
        ),
        (
            "MCP rejects protocol revision drift",
            "mcp-enabled",
            lambda directory: replace_required(
                directory / "RUNTIME.md", "| Supported protocol revisions | `2026-07-28` |",
                "| Supported protocol revisions | `2099-01-01` |",
            ),
            None,
        ),
        (
            "MCP rejects a missing caller-behavior section",
            "mcp-enabled",
            lambda directory: remove_heading_section(
                directory / "MCP_INTERFACE.md", "### Tool-call results and errors"
            ),
            None,
        ),
        (
            "MCP Apps requires MCP_APPS.md",
            "mcp-apps-enabled",
            lambda directory: (directory / "MCP_APPS.md").unlink(),
            None,
        ),
        (
            "MCP Apps rejects browser-interface contract leakage",
            "mcp-apps-enabled",
            lambda directory: (directory / "WEB_INTERFACE.md").write_text(
                "# Unsupported browser contract\n", encoding="utf-8"
            ),
            None,
        ),
        (
            "browser-interface rejects MCP contract leakage",
            "browser-interface",
            lambda directory: (directory / "MCP_INTERFACE.md").write_text(
                "# Unsupported MCP contract\n", encoding="utf-8"
            ),
            None,
        ),
        (
            "browser-interface rejects startup command drift",
            "browser-interface",
            lambda directory: replace_required(
                directory / "RUNTIME.md",
                "| Start human verification Web UI | `TEXT_STATS_WEB_ENABLED=1 python web/server.py` |",
                "| Start human verification Web UI | `python web/other.py` |",
            ),
            None,
        ),
        (
            "headless-service rejects a browser contract",
            "headless-service",
            lambda directory: (directory / "WEB_INTERFACE.md").write_text(
                "# Unsupported browser contract\n", encoding="utf-8"
            ),
            None,
        ),
        (
            "headless-service requires runtime authority",
            "headless-service",
            lambda directory: (directory / "RUNTIME.md").unlink(),
            None,
        ),
    ]

    for name, fixture_name, mutation, diagnostic in cases:
        with tempfile.TemporaryDirectory(prefix="contract-regression") as temporary:
            directory = Path(temporary)
            shutil.copytree(FIXTURES / fixture_name, directory, dirs_exist_ok=True, symlinks=True)
            try:
                mutation(directory)
            except Exception as exc:
                failures.append(f"{name}: mutation setup failed: {exc}")
                continue
            initialize_git(directory)
            result = validate(directory)
            if result.returncode == 0:
                failures.append(f"{name}: expected canonical validation failure")
            elif not result.stderr.strip():
                failures.append(f"{name}: expected actionable diagnostics")
            elif diagnostic and diagnostic.lower() not in result.stderr.lower():
                failures.append(
                    f"{name}: expected diagnostic containing {diagnostic!r}; stderr={result.stderr!r}"
                )

    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    for path in ("README.md", "docs/**", "template/**"):
        if f"- {path}" not in pages:
            failures.append(f"documentation compatibility workflow omits {path}")
    for removed in ("CLI_INTERFACE.md", "MCP_INTERFACE.md", "assets/**"):
        if any(line.strip() == f"- {removed}" for line in pages.splitlines()):
            failures.append(f"documentation compatibility retains removed root filter {removed}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Python-only canonical contract regression tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
