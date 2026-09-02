from __future__ import annotations

import itertools
import shutil
import stat
import tempfile
from pathlib import Path

from ..diagnostics import Diagnostic
from ..lockfile import LOCK_PATH, load_lock_output_paths, resolve_lock_path
from ..paths import resolve_inside
from .render import run as render_run


def _resolve_candidate(repository_root: Path, relative: str) -> Path:
    return resolve_inside(repository_root, relative, allow_missing=True)


def _locked_outputs(repository_root: Path) -> set[str]:
    lock_path = resolve_lock_path(repository_root, allow_missing=True)
    if not lock_path.exists():
        return set()
    outputs = set(load_lock_output_paths(lock_path))
    for relative in outputs:
        _resolve_candidate(repository_root, relative)
    return outputs


def _is_stale(left: Path, right: Path) -> bool:
    return (
        not left.is_file()
        or not right.is_file()
        or left.read_bytes() != right.read_bytes()
    )


def _make_staging_writable(root: Path) -> None:
    for path in itertools.chain((root,), root.rglob("*")):
        if path.is_symlink():
            continue
        mode = path.stat(follow_symlinks=False).st_mode
        if path.is_dir():
            path.chmod(mode | stat.S_IWUSR | stat.S_IXUSR)
        elif path.is_file():
            path.chmod(mode | stat.S_IWUSR)


def run(repository_root: Path, config_path: str) -> list[Diagnostic]:
    try:
        previous_outputs = _locked_outputs(repository_root)
        with tempfile.TemporaryDirectory(prefix="agent-policy-check-") as temporary:
            staged = Path(temporary) / "repo"
            shutil.copytree(repository_root, staged, ignore=shutil.ignore_patterns(".git"))
            # A trusted authority snapshot may deliberately be frozen read-only.
            # Rendering happens only in this disposable copy, so restore owner
            # writability without mutating the reviewed snapshot itself.
            _make_staging_writable(staged)
            diagnostics = render_run(staged, config_path)
            if diagnostics:
                return diagnostics

            expected_outputs = _locked_outputs(staged)
            differences: list[Diagnostic] = []

            for relative in sorted(previous_outputs - expected_outputs):
                differences.append(
                    Diagnostic(
                        "error",
                        "OBSOLETE_OUTPUT",
                        "Previously generated output is no longer declared",
                        relative,
                    )
                )

            for relative in sorted({LOCK_PATH, *expected_outputs}):
                left = _resolve_candidate(repository_root, relative)
                right = _resolve_candidate(staged, relative)
                if _is_stale(left, right):
                    differences.append(
                        Diagnostic("error", "STALE_OUTPUT", "Generated file is stale", relative)
                    )
            return differences
    except Exception as exc:
        return [Diagnostic("error", "CHECK", str(exc))]
