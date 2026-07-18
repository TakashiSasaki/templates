from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..diagnostics import Diagnostic
from .render import run as render_run


def run(repository_root: Path, config_path: str) -> list[Diagnostic]:
    with tempfile.TemporaryDirectory(prefix="agent-policy-check-") as temporary:
        staged = Path(temporary) / "repo"
        shutil.copytree(repository_root, staged, ignore=shutil.ignore_patterns(".git"))
        diagnostics = render_run(staged, config_path)
        if diagnostics:
            return diagnostics
        candidates = [".agent-policy.lock", "AGENTS.md", ".agents/skills"]
        differences: list[Diagnostic] = []
        for relative in candidates:
            left = repository_root / relative
            right = staged / relative
            if left.is_dir() or right.is_dir():
                left_files = (
                    {
                        str(path.relative_to(left)): path.read_bytes()
                        for path in left.rglob("*")
                        if path.is_file()
                    }
                    if left.is_dir()
                    else {}
                )
                right_files = (
                    {
                        str(path.relative_to(right)): path.read_bytes()
                        for path in right.rglob("*")
                        if path.is_file()
                    }
                    if right.is_dir()
                    else {}
                )
                if left_files != right_files:
                    differences.append(
                        Diagnostic(
                            "error",
                            "STALE_OUTPUT",
                            "Generated directory is stale",
                            relative,
                        )
                    )
            elif (
                not left.exists()
                or not right.exists()
                or left.read_bytes() != right.read_bytes()
            ):
                differences.append(
                    Diagnostic("error", "STALE_OUTPUT", "Generated file is stale", relative)
                )
        return differences
