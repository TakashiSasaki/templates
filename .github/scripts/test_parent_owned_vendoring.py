#!/usr/bin/env python3
"""Prove validation of a concrete Skill vendored into a parent Git worktree."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = SOURCE_ROOT / ".github/fixtures/profiles/script-assisted"
VALIDATOR = SOURCE_ROOT / "template/.github/scripts/validate_skill_repository.py"
SKILL_FILES = ["SKILL.md", "scripts/normalize.py"]
FAILURES: list[str] = []


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


def capture(
    *command: str, cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=clean_env(extra_env),
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


def validate(target: Path, outside: Path) -> subprocess.CompletedProcess[str]:
    return capture(
        sys.executable,
        str(VALIDATOR),
        str(target),
        cwd=outside,
    )


def git_index_bytes(repository: Path) -> bytes:
    index_text = run_or_raise(
        "git", "rev-parse", "--git-path", "index", cwd=repository
    ).strip()
    index_path = Path(index_text)
    if not index_path.is_absolute():
        index_path = repository / index_path
    return index_path.read_bytes()


def tracked_skill_entries(repository: Path, prefix: str) -> dict[str, str]:
    output = run_or_raise(
        "git", "ls-files", "--stage", "--", prefix, cwd=repository
    )
    entries: dict[str, str] = {}
    for line in output.splitlines():
        metadata, path = line.split("\t", 1)
        mode, _sha, _stage = metadata.split(" ", 2)
        entries[path] = mode
    return entries


def content_map(root: Path) -> dict[str, bytes]:
    return {relative: (root / relative).read_bytes() for relative in SKILL_FILES}


def exercise_helper(target: Path) -> None:
    input_path = target / "input.txt"
    output_path = target / "output.txt"
    input_path.write_bytes(b"alpha  \r\nbeta\t\r\n")
    before = input_path.read_bytes()
    result = capture(
        sys.executable,
        "scripts/normalize.py",
        "input.txt",
        "output.txt",
        cwd=target,
    )
    output = output_path.read_bytes() if output_path.is_file() else None
    if not (
        result.returncode == 0
        and result.stdout == "output.txt\n"
        and result.stderr == ""
        and output == b"alpha\nbeta\n"
        and input_path.read_bytes() == before
    ):
        FAILURES.append(
            "helper execution failed; "
            f"status={result.returncode!r}, stdout={result.stdout!r}, "
            f"stderr={result.stderr!r}, output={output!r}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="parent-owned-vendoring") as temporary:
        workspace = Path(temporary)
        outside = workspace / "outside"
        source = workspace / "concrete-skill-source"
        archive = workspace / "concrete-skill.tar"
        extracted = workspace / "archive-extracted"
        parent = workspace / "parent-project"
        skill_prefix = ".agents/skills/line-normalization-helper"
        target = parent / skill_prefix

        for path in (outside, source, extracted, parent):
            path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIXTURE, source, dirs_exist_ok=True, symlinks=True)

        run_or_raise("git", "init", "--quiet", cwd=source)
        run_or_raise(
            "git", "config", "user.name", "Parent-owned Vendoring Fixture", cwd=source
        )
        run_or_raise(
            "git", "config", "user.email", "fixture@example.invalid", cwd=source
        )
        run_or_raise("git", "add", ".", cwd=source)
        run_or_raise(
            "git", "commit", "--quiet", "-m", "Create concrete skill", cwd=source
        )
        run_or_raise(
            "git",
            "archive",
            "--format=tar",
            "--prefix=line-normalization-helper/",
            f"--output={archive}",
            "HEAD",
            cwd=source,
        )
        run_or_raise("tar", "-xf", str(archive), "-C", str(extracted), cwd=workspace)

        run_or_raise("git", "init", "--quiet", cwd=parent)
        run_or_raise(
            "git", "config", "user.name", "Parent Project Fixture", cwd=parent
        )
        run_or_raise(
            "git", "config", "user.email", "parent@example.invalid", cwd=parent
        )
        (parent / "README.md").write_text("# Parent project\n", encoding="utf-8")
        run_or_raise("git", "add", "README.md", cwd=parent)
        run_or_raise(
            "git", "commit", "--quiet", "-m", "Create parent project", cwd=parent
        )

        target.mkdir(parents=True)
        shutil.copytree(
            extracted / "line-normalization-helper",
            target,
            dirs_exist_ok=True,
            symlinks=True,
        )
        run_or_raise("git", "add", "--", skill_prefix, cwd=parent)
        run_or_raise(
            "git", "commit", "--quiet", "-m", "Vendor concrete skill", cwd=parent
        )

        expected_entries = {
            f"{skill_prefix}/{relative}": "100644" for relative in SKILL_FILES
        }
        actual_entries = tracked_skill_entries(parent, skill_prefix)
        if actual_entries != expected_entries:
            FAILURES.append(
                "parent index does not own the expected regular files: "
                f"{actual_entries!r}"
            )
        if content_map(target) != content_map(source):
            FAILURES.append("vendored bytes differ from the committed source")
        if (target / ".git").exists():
            FAILURES.append("vendored target unexpectedly contains Git metadata")
        if (target / "line-normalization-helper").is_dir():
            FAILURES.append("vendored target retained an archive wrapper")

        discovered_root = Path(
            run_or_raise("git", "rev-parse", "--show-toplevel", cwd=target).strip()
        )
        if discovered_root.resolve() != parent.resolve():
            FAILURES.append("validator target did not discover the parent worktree")

        index_before = git_index_bytes(parent)
        result = validate(target, outside)
        if not (
            result.returncode == 0
            and result.stderr == ""
            and "Agent Skill repository structure and profile contracts are valid."
            in result.stdout
        ):
            FAILURES.append(
                "expected parent-owned vendored skill validation success; "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}"
            )
        if git_index_bytes(parent) != index_before:
            FAILURES.append("successful validation modified the parent index")
        exercise_helper(target)

        parent_head = run_or_raise("git", "rev-parse", "HEAD", cwd=parent).strip()
        gitlink_path = f"{skill_prefix}/scripts/index-only-link"
        run_or_raise(
            "git",
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{parent_head},{gitlink_path}",
            cwd=parent,
        )
        if (parent / gitlink_path).exists():
            FAILURES.append("index-only gitlink unexpectedly exists on the filesystem")

        gitlink_index_before = git_index_bytes(parent)
        result = validate(target, outside)
        diagnostic = "Operational resource gitlinks are not allowed: scripts/index-only-link"
        if result.returncode == 0:
            FAILURES.append("expected parent-index gitlink rejection")
        elif diagnostic not in result.stderr:
            FAILURES.append(
                f"expected diagnostic {diagnostic!r}; stderr={result.stderr!r}"
            )
        if git_index_bytes(parent) != gitlink_index_before:
            FAILURES.append("failed validation modified the parent index")

    if FAILURES:
        for failure in FAILURES:
            print(failure, file=sys.stderr)
        return 1
    print("Parent-owned vendoring smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
