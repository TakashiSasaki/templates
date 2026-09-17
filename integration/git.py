"""Exact Git checkout identity checks used by Integration semantic readers."""
from __future__ import annotations

import subprocess
from pathlib import Path

from publication_bundle.repository import FULL_SHA, RepositoryInputError


def checked_revision(root: Path) -> str:
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.PIPE,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RepositoryInputError(f"unable to inspect Git repository {root}") from exc
    if not FULL_SHA.fullmatch(revision):
        raise RepositoryInputError(
            f"Git HEAD must resolve to a full lowercase SHA: {root}"
        )
    return revision
