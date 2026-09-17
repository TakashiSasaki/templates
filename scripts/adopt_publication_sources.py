#!/usr/bin/env python3
"""Plan or apply an exact, allowlisted Integration publication lock update."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.resolve_publication_sources import (
    ALL_PUBLICATION_NAMES,
    SourceLockError,
    read_json_object,
    render_source_lock,
    resolve_sources,
)

ALLOWED = {
    "publications.modeling.revision",
    "publications.composition.revision",
    "publications.policy.revision",
    "schema_version",
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(path: Path) -> tuple[dict, bytes]:
    data = read_json_object(path)
    resolved = resolve_sources(path, {})
    canonical = render_source_lock(resolved)
    if path.read_bytes() != canonical:
        raise SourceLockError(f"{path} is not the deterministic source-lock rendering")
    return data, canonical


def plan(current_path: Path, candidate_path: Path) -> dict:
    current, current_bytes = _canonical(current_path)
    candidate, candidate_bytes = _canonical(candidate_path)
    current_publications = current["publications"]
    candidate_publications = candidate["publications"]
    if set(candidate_publications) < set(current_publications):
        raise SourceLockError("candidate removes an already selected provider")
    changed: list[str] = []
    for name in ALL_PUBLICATION_NAMES:
        current_entry = current_publications.get(name)
        candidate_entry = candidate_publications.get(name)
        if current_entry != candidate_entry:
            changed.append(f"publications.{name}.revision")
    if current["schema_version"] != candidate["schema_version"]:
        if (current["schema_version"], candidate["schema_version"]) != (1, 2) or set(candidate_publications) != set(ALL_PUBLICATION_NAMES):
            raise SourceLockError("unsupported publication-lock schema transition")
        changed.append("schema_version")
    unexpected = [field for field in changed if field not in ALLOWED]
    if unexpected:
        raise SourceLockError("candidate changes non-allowlisted fields: " + ", ".join(unexpected))
    return {
        "schema_version": 1,
        "boundary": "provider-to-integration",
        "classification": "NO_CHANGE" if not changed else "AUTO_PROCESSABLE",
        "current_lock_digest": _digest(current_bytes),
        "candidate_lock_digest": _digest(candidate_bytes),
        "changed_fields": changed,
        "allowed_mutations": [f"publication-sources.json:{field}" for field in changed],
        "expected_bytes": candidate_bytes.decode("utf-8"),
    }


def apply(current_path: Path, candidate_path: Path, *, expected_current_digest: str) -> dict:
    result = plan(current_path, candidate_path)
    if result["current_lock_digest"] != expected_current_digest:
        raise SourceLockError("publication source lock changed after the transaction snapshot")
    if result["classification"] == "NO_CHANGE":
        return result
    if _digest(current_path.read_bytes()) != expected_current_digest:
        raise SourceLockError("publication source lock changed before adoption write")
    candidate_bytes = candidate_path.read_bytes()
    with tempfile.NamedTemporaryFile("wb", prefix=".publication-sources-", dir=current_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(candidate_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, current_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    result["applied"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, default=Path("publication-sources.json"))
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
    except (OSError, SourceLockError, ValueError) as exc:
        parser.error(str(exc))
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + chr(10)
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
