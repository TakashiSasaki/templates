#!/usr/bin/env python3
"""Exercise clean-room adoption and installation from a byte-for-byte template copy."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = SOURCE_ROOT / "template"
DISTRIBUTION_VALIDATOR = SOURCE_ROOT / ".github/scripts/validate_skill_distribution.py"
ENGINE_PATHS = {
    ".github/scripts/test_template_adoption.py": "Template adoption smoke tests passed.",
    ".github/scripts/test_installation_modes.py": "Installation mode smoke tests passed.",
}
SOURCE_ONLY_PATHS = (
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "distribution-manifest.json",
    "docs/publication-catalog.json",
    "docs/publication-maintenance.md",
    "docs/architecture/distribution-boundary.md",
    "docs/architecture/distribution-classification.json",
    ".github/REVIEW_GUIDELINES.md",
    ".github/fixtures",
    ".github/workflows/pages.yml",
    ".github/workflows/validate-structure.yml",
    ".github/workflows/validate-portable-consumption.yml",
    ".github/workflows/validate-extended-profile-contracts.yml",
)
VALIDATOR_REWRITE_FROM = 'SOURCE_ROOT / "template/.github/scripts/validate_skill_repository.py"'
VALIDATOR_REWRITE_TO = 'SOURCE_ROOT / ".github/scripts/validate_skill_repository.py"'


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(key, None)
    return env


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
    record: list[Any] = [kind, mode & 0o7777]
    if kind == "file":
        record.append(hashlib.sha256(path.read_bytes()).hexdigest())
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


def copy_template(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE_ROOT, target, dirs_exist_ok=True, symlinks=True)


def adapt_engine_for_distribution(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    if VALIDATOR_REWRITE_FROM not in content:
        raise RuntimeError(
            f"Python engine validator rewrite source is missing in {path.name}"
        )
    path.write_text(
        content.replace(VALIDATOR_REWRITE_FROM, VALIDATOR_REWRITE_TO, 1),
        encoding="utf-8",
    )


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=clean_env(),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def main() -> int:
    failures: list[str] = []
    if not (TEMPLATE_ROOT.is_dir() and (TEMPLATE_ROOT / "SKILL.md").is_file()):
        print(
            f"copyable template root is missing or incomplete: {TEMPLATE_ROOT}",
            file=sys.stderr,
        )
        return 1

    source_before = tree_snapshot(TEMPLATE_ROOT)
    distribution = run(
        [sys.executable, str(DISTRIBUTION_VALIDATOR), str(SOURCE_ROOT)],
        cwd=SOURCE_ROOT,
    )
    if not (
        distribution.returncode == 0
        and distribution.stderr == ""
        and "Skill template distribution is valid." in distribution.stdout
    ):
        failures.append(
            "canonical distribution validation failed: "
            f"status={distribution.returncode!r}, stdout={distribution.stdout!r}, "
            f"stderr={distribution.stderr!r}"
        )

    with tempfile.TemporaryDirectory(prefix="copyable-template-consumption") as temporary:
        workspace = Path(temporary)
        clean_source = workspace / "canonical template source with spaces/日本語"
        copy_template(clean_source)

        copied_before_injection = tree_snapshot(clean_source)
        if copied_before_injection != source_before:
            failures.append(
                "clean-room copy differs from template/ bytes, modes, paths, or link types"
            )
        if (clean_source / "template").is_dir():
            failures.append("copy retained an unexpected template/ wrapper")
        if not (clean_source / "SKILL.md").is_file():
            failures.append("SKILL.md is not directly under the copied root")

        for relative in SOURCE_ONLY_PATHS:
            path = clean_source / relative
            if path.exists() or path.is_symlink():
                failures.append(
                    f"source-only path leaked into copyable template: {relative}"
                )

        for relative in ENGINE_PATHS:
            source = SOURCE_ROOT / relative
            destination = clean_source / relative
            if not (source.is_file() and not source.is_symlink()):
                failures.append(f"missing source-owned consumption engine: {relative}")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            try:
                adapt_engine_for_distribution(destination)
            except RuntimeError as exc:
                failures.append(str(exc))

        for relative, success_line in ENGINE_PATHS.items():
            engine = clean_source / relative
            if not engine.is_file():
                continue
            result = run([sys.executable, str(engine)], cwd=clean_source)
            last_line = result.stdout.splitlines()[-1] if result.stdout.splitlines() else None
            if not (
                result.returncode == 0
                and result.stderr == ""
                and last_line == success_line
            ):
                failures.append(
                    f"{relative} failed from the clean-room template copy: "
                    f"status={result.returncode!r}, stdout={result.stdout!r}, "
                    f"stderr={result.stderr!r}"
                )

    source_after = tree_snapshot(TEMPLATE_ROOT)
    if source_after != source_before:
        failures.append("consumption validation mutated template/")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Copyable template adoption and installation tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
