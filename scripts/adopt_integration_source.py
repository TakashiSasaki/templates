#!/usr/bin/env python3
"""Produce a guarded Site Integration-lock adoption transaction.

The default is a read-only plan. --apply is intentionally explicit and
still requires the caller to bind the write to the exact current lock bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from site_renderer.bundle import BundleError, load_lock

ALLOWED_FIELDS = ("revision", "bundle_schema", "bundle_identity", "content_digest")


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_lock(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def plan(current_path: Path, candidate_path: Path) -> dict:
    current_bytes = current_path.read_bytes()
    candidate_bytes = candidate_path.read_bytes()
    if current_path.is_symlink() or candidate_path.is_symlink():
        raise BundleError("lock inputs must not be symbolic links")
    current = load_lock(current_path)
    candidate = load_lock(candidate_path)
    if candidate_bytes != _canonical_lock(candidate):
        raise BundleError("candidate lock is not the deterministic renderer output")
    if set(current) != set(candidate):
        raise BundleError("candidate lock shape differs from current lock")
    changed = [key for key in current if current[key] != candidate[key]]
    unexpected = [key for key in changed if key not in ALLOWED_FIELDS]
    if unexpected:
        raise BundleError("candidate changes non-allowlisted lock fields: " + ", ".join(unexpected))
    classification = "NO_CHANGE" if not changed else "AUTO_PROCESSABLE"
    return {
        "schema_version": 1,
        "boundary": "integration-to-site",
        "classification": classification,
        "current_lock_digest": _digest(current_bytes),
        "candidate_lock_digest": _digest(candidate_bytes),
        "changed_fields": changed,
        "allowed_mutations": [f"integration-source.json:{field}" for field in changed],
        "expected_bytes": candidate_bytes.decode("utf-8"),
    }


def apply(current_path: Path, candidate_path: Path, *, expected_current_digest: str) -> dict:
    result = plan(current_path, candidate_path)
    if result["current_lock_digest"] != expected_current_digest:
        raise BundleError("current lock changed after the transaction snapshot")
    if result["classification"] == "NO_CHANGE":
        return result
    candidate_bytes = candidate_path.read_bytes()
    mode = current_path.stat().st_mode & 0o777
    if _digest(current_path.read_bytes()) != expected_current_digest:
        raise BundleError("current lock changed before adoption write")
    with tempfile.NamedTemporaryFile("wb", prefix=".integration-source-", dir=current_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(candidate_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    try:
        os.replace(temporary, current_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    result["applied"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, default=Path("integration-source.json"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-current-digest")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.apply and not args.expected_current_digest:
            parser.error("--apply requires --expected-current-digest")
        result = (apply(args.current, args.candidate, expected_current_digest=args.expected_current_digest)
                  if args.apply else plan(args.current, args.candidate))
    except (OSError, BundleError, ValueError) as exc:
        parser.error(str(exc))
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
