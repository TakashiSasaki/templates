#!/usr/bin/env python3
"""Verify that tracked repository tooling no longer depends on Ruby."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SUFFIXES = {".yml", ".yaml"}
RUNTIME_COMMAND = re.compile(
    r"(?:^|[;&|]\s*)(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*"
    r"(?:sudo\s+)?(?:ruby|bundle|bundler|gem|rake)(?=\s|$)",
    re.IGNORECASE,
)
RUBY_SHEBANG = re.compile(rb"^#![^\r\n]*\bruby(?=\s|$)", re.IGNORECASE)


def _tracked_paths() -> tuple[list[str], str | None]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return [], "Unable to enumerate tracked files."
    try:
        paths = [raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw]
    except UnicodeDecodeError:
        return [], "Tracked path list is not valid UTF-8."
    return paths, None


def _scan_workflow(relative: str, data: bytes) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"Workflow is not valid UTF-8: {relative}"]

    failures: list[str] = []
    if "ruby/setup-ruby" in text.lower():
        failures.append(f"Ruby setup action remains: {relative}")

    run_block_indent: int | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip())

        if run_block_indent is not None:
            if stripped and indent <= run_block_indent:
                run_block_indent = None
            elif stripped and not stripped.startswith("#"):
                if RUNTIME_COMMAND.search(stripped):
                    failures.append(
                        f"Ruby workflow command remains: {relative}:{line_number}: {stripped}"
                    )
                continue

        if not stripped or stripped.startswith("#"):
            continue

        lowered = stripped.lower()
        if lowered.startswith("shell:") and "ruby" in lowered.split(":", 1)[1]:
            failures.append(
                f"Ruby workflow shell remains: {relative}:{line_number}: {stripped}"
            )
            continue

        if not lowered.startswith("run:"):
            continue
        command = stripped.split(":", 1)[1].strip()
        if command in {"|", "|-", "|+", ">", ">-", ">+"}:
            run_block_indent = indent
            continue
        if RUNTIME_COMMAND.search(command):
            failures.append(
                f"Ruby workflow command remains: {relative}:{line_number}: {command}"
            )

    return failures


def main() -> int:
    tracked, error = _tracked_paths()
    if error:
        print(error, file=sys.stderr)
        return 1

    failures: list[str] = []
    for relative in tracked:
        path = PurePosixPath(relative)
        if path.suffix.lower() in {".rb", ".rake", ".gemspec"}:
            failures.append(f"Ruby tooling path remains: {relative}")
        if path.name in {"Gemfile", "Gemfile.lock", "Rakefile", ".ruby-version"}:
            failures.append(f"Ruby tooling path remains: {relative}")
        if ".bundle" in path.parts:
            failures.append(f"Ruby tooling path remains: {relative}")

        candidate = ROOT / relative
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            data = candidate.read_bytes()
        except OSError as exc:
            failures.append(f"Unable to inspect tracked file {relative}: {exc}")
            continue

        first_line = data.splitlines()[0] if data.splitlines() else b""
        if RUBY_SHEBANG.search(first_line):
            failures.append(f"Ruby shebang remains: {relative}")

        if (
            len(path.parts) >= 2
            and path.parts[0] == ".github"
            and path.suffix.lower() in WORKFLOW_SUFFIXES
        ):
            failures.extend(_scan_workflow(relative, data))

    if failures:
        for failure in sorted(set(failures)):
            print(failure, file=sys.stderr)
        return 1

    print("No active Ruby tooling remains in tracked paths, shebangs, or workflow commands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
