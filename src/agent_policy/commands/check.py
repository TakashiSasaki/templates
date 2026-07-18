from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..diagnostics import Diagnostic
from ..lockfile import load_lock_output_paths
from ..paths import resolve_inside
from .render import run as render_run

LOCK_PATH = ".agent-policy.lock"


def _locked_outputs(repository_root: Path) -> set[str]:
    lock_path = repository_root / LOCK_PATH
    if not lock_path.exists():
        return set()
    return set(load_lock_output_paths(lock_path))


def _resolve_candidate(repository_root: Path, relative: str) -> Path:
    return resolve_inside(repository_root, relative, allow_missing=True)


def _is_stale(left: Path, right: Path) -> bool:
    return (
        not left.is_file()
        or not right.is_file()
        or left.read_bytes() != right.read_bytes()
    )


def run(repository_root: Path, config_path: str) -> list[Diagnostic]:
    try:
        previous_outputs = _locked_outputs(repository_root)
        with tempfile.TemporaryDirectory(prefix="agent-policy-check-") as temporary:
            staged = Path(temporary) / "repo"
            shutil.copytree(repository_root, staged, ignore=shutil.ignore_patterns(".git"))
            diagnostics = render_run(staged, config_path)
            if diagnostics:
                return diagnostics

            expected_outputs = _locked_outputs(staged)
            differences: list[Diagnostic] = []

            for relative in sorted(previous_outputs - expected_outputs):
                _resolve_candidate(repository_root, relative)
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
