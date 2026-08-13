#!/usr/bin/env python3
"""Prove validation and bounded helper execution do not mutate unrelated state."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = SOURCE_ROOT / ".github/fixtures/profiles/script-assisted"
COMBINED_FIXTURE = SOURCE_ROOT / ".github/fixtures/profiles/combined-resources"
VALIDATOR = SOURCE_ROOT / "template/.github/scripts/validate_skill_repository.py"
FAILURES: list[str] = []


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    return env


def capture(*command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=clean_env(),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def run_or_raise(*command: str, cwd: Path) -> str:
    result = capture(*command, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {command!r}; status={result.returncode!r}; "
            f"stdout={result.stdout!r}; stderr={result.stderr!r}"
        )
    return result.stdout


def git_run_or_raise(*arguments: str, cwd: Path) -> str:
    return run_or_raise("git", *arguments, cwd=cwd)


def _snapshot_entry(path: Path) -> tuple[Any, ...]:
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


def tree_snapshot(root: Path, *, exclude: tuple[str, ...] = ()) -> dict[str, tuple[Any, ...]]:
    excluded = {str((root / relative).absolute()) for relative in exclude}
    snapshot: dict[str, tuple[Any, ...]] = {".": _snapshot_entry(root)}

    def visit(directory: Path) -> None:
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            absolute = str(path.absolute())
            if any(absolute == item or absolute.startswith(item + os.sep) for item in excluded):
                continue
            relative = path.relative_to(root).as_posix()
            snapshot[relative] = _snapshot_entry(path)
            if entry.is_dir(follow_symlinks=False):
                visit(path)

    visit(root)
    return snapshot


def git_index_bytes(repository: Path) -> bytes:
    text = git_run_or_raise("rev-parse", "--git-path", "index", cwd=repository).strip()
    path = Path(text)
    if not path.is_absolute():
        path = repository / path
    return path.read_bytes()


def context_snapshot(target: Path, parent: Path, outside: Path) -> dict[str, Any]:
    return {
        "skill": tree_snapshot(target),
        "parent": tree_snapshot(parent, exclude=(".git",)),
        "outside": tree_snapshot(outside),
        "index": git_index_bytes(parent),
    }


def expect_context_unchanged(
    label: str,
    target: Path,
    parent: Path,
    outside: Path,
    expected: dict[str, Any],
) -> None:
    actual = context_snapshot(target, parent, outside)
    if actual["skill"] != expected["skill"]:
        FAILURES.append(f"{label}: installed skill tree changed")
    if actual["parent"] != expected["parent"]:
        FAILURES.append(f"{label}: parent worktree changed outside .git")
    if actual["outside"] != expected["outside"]:
        FAILURES.append(f"{label}: unrelated working directory changed")
    if actual["index"] != expected["index"]:
        FAILURES.append(f"{label}: parent Git index changed")


def expect_only_declared_output(
    label: str,
    root: Path,
    before: dict[str, tuple[Any, ...]],
    output_relative: str,
    expected_bytes: bytes,
) -> None:
    after = tree_snapshot(root)
    if list(after) != list(before):
        FAILURES.append(
            f"{label}: caller-owned inventory changed: "
            f"before={list(before)!r}, after={list(after)!r}"
        )
        return
    for relative, record in before.items():
        if relative == output_relative:
            continue
        if relative == ".":
            if after[relative][:2] != record[:2]:
                FAILURES.append(f"{label}: caller-owned root type or permissions changed")
        elif after[relative] != record:
            FAILURES.append(f"{label}: caller-owned entry changed: {relative}")
    output_after = after[output_relative]
    if not (output_after[0] == "file" and output_after[3] == expected_bytes):
        FAILURES.append(f"{label}: declared output did not match its contract")


def validate(target: Path, outside: Path) -> subprocess.CompletedProcess[str]:
    return capture(sys.executable, str(VALIDATOR), str(target), cwd=outside)


def run_helper(target: Path, input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return capture(
        sys.executable,
        "scripts/normalize.py",
        str(input_path),
        str(output_path),
        cwd=target,
    )


def expect_alias_rejection(
    label: str,
    target: Path,
    input_path: Path,
    output_path: Path,
    area: Path,
    expected_context: dict[str, Any],
    parent: Path,
    outside: Path,
) -> None:
    area_before = tree_snapshot(area)
    result = run_helper(target, input_path, output_path)
    area_after = tree_snapshot(area)
    diagnostic = "input and output must refer to different files"
    if not (
        result.returncode == 2
        and result.stdout == ""
        and diagnostic in result.stderr
        and area_after == area_before
    ):
        FAILURES.append(
            f"{label}: aliased paths were not rejected without mutation: "
            f"status={result.returncode!r}, stdout={result.stdout!r}, "
            f"stderr={result.stderr!r}, area_unchanged={area_after == area_before}"
        )
    expect_context_unchanged(label, target, parent, outside, expected_context)


def expect_local_alias_rejection(
    label: str, target: Path, input_path: Path, output_path: Path, area: Path
) -> None:
    before = tree_snapshot(area)
    result = run_helper(target, input_path, output_path)
    after = tree_snapshot(area)
    diagnostic = "input and output must refer to different files"
    if not (
        result.returncode == 2
        and result.stdout == ""
        and diagnostic in result.stderr
        and after == before
    ):
        FAILURES.append(
            f"{label}: aliased paths were not rejected without mutation: "
            f"status={result.returncode!r}, stdout={result.stdout!r}, "
            f"stderr={result.stderr!r}, area_unchanged={after == before}"
        )


def exercise_alias_contract(label: str, fixture: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{label}-alias-contract") as temporary:
        workspace = Path(temporary)
        target = workspace / "skill"
        same_area = workspace / "same-path"
        hard_area = workspace / "hard-link"
        for path in (target, same_area, hard_area):
            path.mkdir(parents=True)
        shutil.copytree(fixture, target, dirs_exist_ok=True, symlinks=True)

        same_path = same_area / "same.txt"
        same_path.write_bytes(b"same-path input\r\n")
        expect_local_alias_rejection(
            f"{label} same-path rejection", target, same_path, same_path, same_area
        )

        hard_input = hard_area / "input.txt"
        hard_output = hard_area / "output.txt"
        hard_input.write_bytes(b"hard-link input\r\n")
        os.link(hard_input, hard_output)
        if not os.path.samefile(hard_input, hard_output):
            FAILURES.append(f"{label}: hard-link alias fixture does not identify the same file")
        expect_local_alias_rejection(
            f"{label} hard-link rejection",
            target,
            hard_input,
            hard_output,
            hard_area,
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="non-mutating-consumption") as temporary:
        workspace = Path(temporary)
        outside = workspace / "outside"
        parent = workspace / "parent-project"
        caller_root = workspace / "caller-owned"
        success_area = caller_root / "success"
        failure_area = caller_root / "failure"
        same_alias_area = caller_root / "same-path-alias"
        hard_alias_area = caller_root / "hard-link-alias"
        skill_prefix = ".agents/skills/line-normalization-helper"
        target = parent / skill_prefix
        for path in (
            outside,
            target,
            success_area,
            failure_area,
            same_alias_area,
            hard_alias_area,
        ):
            path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIXTURE, target, dirs_exist_ok=True, symlinks=True)

        git_run_or_raise("init", "--quiet", cwd=parent)
        git_run_or_raise(
            "config", "user.name", "Non-mutating Consumption Fixture", cwd=parent
        )
        git_run_or_raise(
            "config", "user.email", "fixture@example.invalid", cwd=parent
        )
        (parent / "README.md").write_text("# Parent project\n", encoding="utf-8")
        git_run_or_raise("add", ".", cwd=parent)
        git_run_or_raise(
            "commit", "--quiet", "-m", "Install concrete skill", cwd=parent
        )

        baseline = context_snapshot(target, parent, outside)
        result = validate(target, outside)
        if not (
            result.returncode == 0
            and result.stderr == ""
            and "Agent Skill repository structure and profile contracts are valid."
            in result.stdout
        ):
            FAILURES.append(
                "successful validation failed: "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}"
            )
        expect_context_unchanged("successful validation", target, parent, outside, baseline)

        input_path = success_area / "input.txt"
        output_path = success_area / "output.txt"
        input_path.write_bytes(b"alpha  \r\nbeta\t\r\n")
        output_path.write_bytes(b"stale output\n")
        success_before = tree_snapshot(success_area)
        result = run_helper(target, input_path, output_path)
        output = output_path.read_bytes() if output_path.is_file() else None
        if not (
            result.returncode == 0
            and result.stdout == f"{output_path}\n"
            and result.stderr == ""
            and output == b"alpha\nbeta\n"
        ):
            FAILURES.append(
                "successful helper execution failed: "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}, output={output!r}"
            )
        expect_only_declared_output(
            "successful helper execution",
            success_area,
            success_before,
            "output.txt",
            b"alpha\nbeta\n",
        )
        expect_context_unchanged(
            "successful helper execution", target, parent, outside, baseline
        )

        invalid_input = failure_area / "invalid.bin"
        invalid_output = failure_area / "invalid-output.txt"
        invalid_input.write_bytes(b"\xff")
        failure_before = tree_snapshot(failure_area)
        result = run_helper(target, invalid_input, invalid_output)
        failure_after = tree_snapshot(failure_area)
        if not (
            result.returncode == 3
            and result.stdout == ""
            and "invalid UTF-8 input" in result.stderr
            and not invalid_output.exists()
            and failure_after == failure_before
        ):
            FAILURES.append(
                "failed helper execution did not preserve its boundary: "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}, caller_area_unchanged={failure_after == failure_before}"
            )
        expect_context_unchanged(
            "failed helper execution", target, parent, outside, baseline
        )

        same_path = same_alias_area / "same.txt"
        same_path.write_bytes(b"same-path input\r\n")
        expect_alias_rejection(
            "same-path helper rejection",
            target,
            same_path,
            same_path,
            same_alias_area,
            baseline,
            parent,
            outside,
        )

        hard_input = hard_alias_area / "input.txt"
        hard_output = hard_alias_area / "output.txt"
        hard_input.write_bytes(b"hard-link input\r\n")
        os.link(hard_input, hard_output)
        if not os.path.samefile(hard_input, hard_output):
            FAILURES.append("hard-link alias fixture does not identify the same file")
        expect_alias_rejection(
            "hard-link helper rejection",
            target,
            hard_input,
            hard_output,
            hard_alias_area,
            baseline,
            parent,
            outside,
        )

        parent_head = git_run_or_raise("rev-parse", "HEAD", cwd=parent).strip()
        gitlink_path = f"{skill_prefix}/scripts/index-only-link"
        git_run_or_raise(
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{parent_head},{gitlink_path}",
            cwd=parent,
        )
        gitlink_index = git_index_bytes(parent)
        if (parent / gitlink_path).exists():
            FAILURES.append("index-only gitlink unexpectedly exists on the filesystem")

        result = validate(target, outside)
        diagnostic = "Operational resource gitlinks are not allowed: scripts/index-only-link"
        if result.returncode == 0:
            FAILURES.append("expected validation failure for index-only gitlink")
        elif diagnostic not in result.stderr:
            FAILURES.append(
                f"expected diagnostic {diagnostic!r}; stderr={result.stderr!r}"
            )
        failed_expected = dict(baseline)
        failed_expected["index"] = gitlink_index
        expect_context_unchanged(
            "failed validation", target, parent, outside, failed_expected
        )

    exercise_alias_contract("combined-resources helper", COMBINED_FIXTURE)

    if FAILURES:
        for failure in FAILURES:
            print(failure, file=sys.stderr)
        return 1
    print("Non-mutating skill consumption smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
