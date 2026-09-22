#!/usr/bin/env python3
"""Candidate bootstrap runner for Policy maintainer workflow execution.

Before B1 adoption, this runner is a candidate bootstrap implementation undergoing
prospective qualification; once adopted, the trust root is anchored to the accepted Policy
authority revision.

Finite trust root chain:
  accepted Policy authority revision
        ↓
  adopted bootstrap / verifier
        ↓
  immutable source manifest
        ↓
  verified maintainer Skill closure
        ↓
  isolated workflow execution

Guarantees:
1. Resolves immutable source manifest from trusted base or explicit prospective manifest.
2. Verifies all declared closure blobs against immutable local Git objects.
3. Materializes verified closure in an IsolatedClosureEnvironment.
4. Executes the verified maintain_review_stack.py entrypoint inside the active isolation lifetime.
5. Ignores mutable worktree entrypoint and sibling files.
6. Cleans up isolated materialization and restores caller sys.modules and sys.path.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

BOOTSTRAP_DIR = Path(__file__).resolve().parent
if str(BOOTSTRAP_DIR) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_DIR))

from verify_maintainer_source_reference import (  # noqa: E402
    CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
    CANONICAL_SOURCE_MANIFEST_PATH,
    FULL_SHA,
    IsolatedClosureEnvironment,
    SourceReferenceError,
    load_source_reference_from_trusted_base,
    verify_trusted_source_reference,
)


def _discover_repo_root(hint: Path | None = None) -> Path:
    target = hint or Path.cwd()
    try:
        toplevel = subprocess.check_output(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
        return Path(toplevel).resolve()
    except (subprocess.CalledProcessError, OSError):
        return BOOTSTRAP_DIR.parent.resolve()


def build_bootstrap_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--trusted-base-sha",
        required=True,
        help="trusted immutable base commit SHA containing source manifest",
    )
    parser.add_argument(
        "--source-manifest",
        help=(
            "optional explicit path to source reference JSON "
            "(default: .agents/skills/land-templates-stack/source.json at trusted base)"
        ),
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        help="path to repository root (default: discovered from current directory)",
    )
    return parser


def run_maintainer_workflow(argv: Sequence[str] | None = None) -> int:
    """Execute the maintainer workflow strictly within the verified closure lifetime."""
    args_list = list(argv if argv is not None else sys.argv[1:])

    bootstrap_parser = build_bootstrap_parser()
    bootstrap_args, _ = bootstrap_parser.parse_known_args(args_list)

    trusted_base_sha = bootstrap_args.trusted_base_sha
    if not FULL_SHA.fullmatch(trusted_base_sha):
        print(
            f"ERROR BOOTSTRAP: trusted base SHA must be a full lowercase SHA: {trusted_base_sha}",
            file=sys.stderr,
        )
        return 2

    repo_root = _discover_repo_root(bootstrap_args.repository_root)

    try:
        if bootstrap_args.source_manifest and Path(bootstrap_args.source_manifest).is_file():
            import json

            manifest_data = json.loads(
                Path(bootstrap_args.source_manifest).read_text(encoding="utf-8")
            )
        else:
            manifest_path = (
                bootstrap_args.source_manifest or CANONICAL_SOURCE_MANIFEST_PATH
            )
            manifest_data = load_source_reference_from_trusted_base(
                repo_root, trusted_base_sha, manifest_path=manifest_path
            )

        verified = verify_trusted_source_reference(manifest_data, repo=repo_root)
    except (SourceReferenceError, ValueError, RuntimeError) as exc:
        print(
            f"ERROR BOOTSTRAP: source reference verification failed: {exc}",
            file=sys.stderr,
        )
        return 2

    forwarded_args = list(args_list)
    if "--repository-root" not in forwarded_args:
        forwarded_args.extend(["--repository-root", str(repo_root)])

    try:
        with IsolatedClosureEnvironment(verified, repo=repo_root) as env:
            return env.run_entrypoint(CANONICAL_MAINTAINER_ENTRYPOINT_PATH, forwarded_args)
    except (SourceReferenceError, ValueError, RuntimeError) as exc:
        print(
            f"ERROR BOOTSTRAP: execution failed: {exc}",
            file=sys.stderr,
        )
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    return run_maintainer_workflow(argv)


if __name__ == "__main__":
    raise SystemExit(main())
