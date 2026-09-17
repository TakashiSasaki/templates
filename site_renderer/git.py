"""Small Site-owned Git identity helpers used during source-link rewriting."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")


class SiteGitError(RuntimeError):
    """Raised when the immutable Site checkout cannot be inspected safely."""


def checked_revision(root: Path) -> str:
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SiteGitError(f"unable to determine Site revision: {root}") from exc
    if FULL_SHA.fullmatch(revision) is None:
        raise SiteGitError("Site revision is not a full lowercase commit SHA")
    return revision


def tracked_paths(root: Path) -> frozenset[bytes]:
    """Return regular tracked source paths without inspecting provider history."""
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "-z"],
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SiteGitError(f"unable to enumerate Site sources: {root}") from exc
    return frozenset(path for path in raw.split(b"\0") if path)
