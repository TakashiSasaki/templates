#!/usr/bin/env python3
"""Rerun portable core smokes beneath paths with spaces and non-ASCII text."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
NON_MUTATING_SMOKE = ".github/scripts/test_non_mutating_consumption.py"
SMOKES = {
    ".github/scripts/test_minimal_profile_layouts.py": "Minimal profile repository layout tests passed.",
    ".github/scripts/test_copyable_template_consumption.py": "Copyable template adoption and installation tests passed.",
    ".github/scripts/test_concrete_skill_completion.py": "Concrete skill completion hygiene tests passed.",
    ".github/scripts/test_parent_owned_vendoring.py": "Parent-owned vendoring smoke tests passed.",
    NON_MUTATING_SMOKE: "Non-mutating skill consumption smoke tests passed.",
}


def snapshot_record(path: Path) -> tuple[Any, ...]:
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode) | (info.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX))
    if stat.S_ISDIR(info.st_mode):
        kind = "directory"
    elif stat.S_ISREG(info.st_mode):
        kind = "file"
    elif stat.S_ISLNK(info.st_mode):
        kind = "symlink"
    else:
        kind = "other"
    record: list[Any] = [kind, mode & 0o7777, info.st_mtime_ns]
    if kind == "file":
        record.append(path.read_bytes())
    elif kind == "symlink":
        record.append(os.readlink(path))
    return tuple(record)


def tree_snapshot(root: Path) -> dict[str, tuple[Any, ...]]:
    snapshot: dict[str, tuple[Any, ...]] = {".": snapshot_record(root)}

    def visit(directory: Path) -> None:
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            snapshot[relative] = snapshot_record(path)
            if entry.is_dir(follow_symlinks=False):
                visit(path)

    visit(root)
    return snapshot


def run(
    command: list[str], *, cwd: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(environment)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="path-safe-consumption-host") as temporary:
        host_root = Path(temporary)
        path_safe_root = host_root / "workspace with spaces/日本語"
        poison_root = host_root / "caller-owned-git-context"
        poison_git_dir = poison_root / "git-dir"
        poison_work_tree = poison_root / "work-tree"
        poison_index = poison_root / "index"
        for path in (path_safe_root, poison_git_dir, poison_work_tree):
            path.mkdir(parents=True, exist_ok=True)
        poison_index.write_bytes(b"caller-owned index sentinel\n")
        (poison_git_dir / "sentinel").write_bytes(b"git-dir sentinel\n")
        (poison_work_tree / "sentinel").write_bytes(b"work-tree sentinel\n")
        poison_before = tree_snapshot(poison_root)

        expected_root = str(path_safe_root.resolve())
        environment = {
            "TMPDIR": str(path_safe_root),
            "TMP": str(path_safe_root),
            "TEMP": str(path_safe_root),
        }
        temp_check = run(
            [
                sys.executable,
                "-c",
                "import os,tempfile; print(os.path.realpath(tempfile.gettempdir()), end='')",
            ],
            cwd=SOURCE_ROOT,
            environment=environment,
        )
        if not (
            temp_check.returncode == 0
            and temp_check.stderr == ""
            and temp_check.stdout == expected_root
        ):
            failures.append(
                "temporary-root selection failed: "
                f"status={temp_check.returncode!r}, stdout={temp_check.stdout!r}, "
                f"stderr={temp_check.stderr!r}, expected={expected_root!r}"
            )

        for relative_script, success_line in SMOKES.items():
            smoke_environment = dict(environment)
            if relative_script == NON_MUTATING_SMOKE:
                smoke_environment.update(
                    {
                        "GIT_DIR": str(poison_git_dir),
                        "GIT_INDEX_FILE": str(poison_index),
                        "GIT_WORK_TREE": str(poison_work_tree),
                    }
                )
            result = run(
                [sys.executable, relative_script],
                cwd=SOURCE_ROOT,
                environment=smoke_environment,
            )
            last_line = result.stdout.splitlines()[-1] if result.stdout.splitlines() else None
            if not (
                result.returncode == 0
                and result.stderr == ""
                and last_line == success_line
            ):
                failures.append(
                    f"{relative_script} failed under path-safe temporary root: "
                    f"status={result.returncode!r}, stdout={result.stdout!r}, "
                    f"stderr={result.stderr!r}"
                )
            if (
                relative_script == NON_MUTATING_SMOKE
                and tree_snapshot(poison_root) != poison_before
            ):
                failures.append(
                    f"{relative_script} mutated inherited caller-owned Git context"
                )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Path-safe core consumption smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
