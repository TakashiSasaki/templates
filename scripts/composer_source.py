#!/usr/bin/env python3
"""Source identity, authority, and revision-transition services for Composition."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class SourceContextError(RuntimeError):
    """Fail-closed source-context diagnostic independent of Composer presentation."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GitSourceContext:
    """Reviewed-checkout source context used by Composition authority maintainers.

    Normal consumers will use a snapshot-backed implementation. Keeping the Git
    implementation behind this boundary prevents Composer semantics from depending
    directly on checkout mechanics.
    """

    root: Path

    def run_git(
        self,
        *arguments: str,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *arguments],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise SourceContextError(
                "GIT_UNAVAILABLE",
                f"cannot execute git: {exc}",
            ) from exc
        if result.returncode != 0 and not allow_failure:
            raise SourceContextError(
                "GIT_FAILED",
                f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
            )
        return result

    def revision(self) -> str:
        revision = self.run_git("rev-parse", "HEAD").stdout.strip()
        if FULL_SHA.fullmatch(revision) is None or revision == "0" * 40:
            raise SourceContextError(
                "INVALID_SOURCE_REVISION",
                f"invalid source revision: {revision!r}",
            )
        dirty = self.run_git(
            "status",
            "--porcelain",
            "--untracked-files=no",
        ).stdout.strip()
        if dirty:
            raise SourceContextError(
                "DIRTY_SOURCE",
                "composition source checkout has tracked modifications; "
                "commit or discard them before composing",
            )
        return revision

    def assert_authority(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise SourceContextError(
                "SOURCE_OUTSIDE_REPOSITORY",
                f"source authority is outside the composition checkout: {path}",
            ) from exc
        if path.is_symlink() or not path.is_file():
            raise SourceContextError(
                "INVALID_SOURCE_AUTHORITY",
                f"source authority must be a regular non-symlink file: {relative}",
            )
        tracked = self.run_git(
            "ls-files",
            "--error-unmatch",
            "--",
            relative,
            allow_failure=True,
        )
        if tracked.returncode != 0:
            raise SourceContextError(
                "UNTRACKED_SOURCE_AUTHORITY",
                "source authority is not tracked by the bound Git revision: "
                f"{relative}",
            )

    def verify_descendant(self, old_revision: str, new_revision: str) -> None:
        if FULL_SHA.fullmatch(old_revision) is None:
            raise SourceContextError(
                "OLD_SOURCE_REVISION_UNAVAILABLE",
                "old composition source revision is invalid or unavailable: "
                f"{old_revision}",
            )
        if FULL_SHA.fullmatch(new_revision) is None:
            raise SourceContextError(
                "INVALID_SOURCE_REVISION",
                f"invalid source revision: {new_revision!r}",
            )
        exists = self.run_git(
            "cat-file",
            "-e",
            f"{old_revision}^{{commit}}",
            allow_failure=True,
        )
        if exists.returncode != 0:
            raise SourceContextError(
                "OLD_SOURCE_REVISION_UNAVAILABLE",
                "old composition source revision is not available in the local "
                f"source history: {old_revision}",
            )
        ancestry = self.run_git(
            "merge-base",
            "--is-ancestor",
            old_revision,
            new_revision,
            allow_failure=True,
        )
        if ancestry.returncode == 1:
            raise SourceContextError(
                "SOURCE_REVISION_NOT_DESCENDANT",
                "target composition source revision "
                f"{new_revision} is not a descendant of old revision {old_revision}",
            )
        if ancestry.returncode != 0:
            raise SourceContextError(
                "GIT_FAILED",
                "cannot establish source revision ancestry for managed operation",
            )
