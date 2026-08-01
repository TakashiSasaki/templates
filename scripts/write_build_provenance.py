#!/usr/bin/env python3
"""Write deterministic source provenance into a generated Pages artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FULL_COMMIT_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")
REPOSITORY_PATTERN = re.compile(
    r"\A[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?/"
    r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?\Z"
)


class ProvenanceError(RuntimeError):
    """Raised when build provenance inputs or output are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--site-commit", required=True)
    parser.add_argument("--canonical-source-commit", required=True)
    return parser.parse_args()


def validate_repository(value: str) -> str:
    if not REPOSITORY_PATTERN.fullmatch(value):
        raise ProvenanceError("repository must be an owner/name identifier")
    return value


def validate_commit(value: str, description: str) -> str:
    if not FULL_COMMIT_PATTERN.fullmatch(value):
        raise ProvenanceError(
            f"{description} must be a full lowercase 40-character Git commit SHA"
        )
    return value


def write_provenance(
    output: Path,
    repository: str,
    site_commit: str,
    canonical_source_commit: str,
) -> None:
    repository = validate_repository(repository)
    site_commit = validate_commit(site_commit, "site commit")
    canonical_source_commit = validate_commit(
        canonical_source_commit, "canonical source commit"
    )

    parent = output.parent
    if not parent.is_dir():
        raise ProvenanceError(f"output directory does not exist: {parent}")
    if output.is_symlink():
        raise ProvenanceError(f"output path must not be a symbolic link: {output}")
    if output.exists() and not output.is_file():
        raise ProvenanceError(f"output path must be a regular file: {output}")

    payload = {
        "schema_version": 1,
        "repository": repository,
        "site_commit": site_commit,
        "canonical_source_commit": canonical_source_commit,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    try:
        write_provenance(
            args.output,
            args.repository,
            args.site_commit,
            args.canonical_source_commit,
        )
    except (OSError, ProvenanceError) as exc:
        print(f"Build provenance generation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote build provenance to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
