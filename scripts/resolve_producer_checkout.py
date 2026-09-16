#!/usr/bin/env python3
"""Resolve the exact commit checked out for Integration qualification."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")


class ProducerCheckoutError(RuntimeError):
    """Raised when a checked-out Producer revision cannot be proven immutable."""


def resolve_checkout(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD^{commit}"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ProducerCheckoutError(f"unable to execute Git: {exc}") from exc
    revision = completed.stdout.strip()
    if completed.returncode != 0 or FULL_SHA.fullmatch(revision) is None:
        detail = completed.stderr.strip() or "Git did not return a full commit SHA"
        raise ProducerCheckoutError(f"unable to resolve checked-out Producer revision: {detail}")
    return revision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", help="Expected full producer revision; mutable references are rejected")
    args = parser.parse_args()
    try:
        revision = resolve_checkout(args.root)
        if args.expected is not None and (FULL_SHA.fullmatch(args.expected) is None or args.expected != revision):
            raise ProducerCheckoutError("producer checkout does not match exact expected revision")
        with args.output.open("a", encoding="utf-8") as output:
            output.write(f"sha={revision}\n")
    except (OSError, ProducerCheckoutError) as exc:
        print(f"Producer checkout resolution failed: {exc}", file=sys.stderr)
        return 1
    print(f"PRODUCER_CHECKOUT_REVISION sha={revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
