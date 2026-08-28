#!/usr/bin/env python3
"""Render exact-candidate verification as a structured provider action result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from candidate import CandidateError, verify_candidate


RESULT_SCHEMA = ".template-composition/release-candidate-verification.schema.json"


def _emit(status: str, revision: str, error: str | None = None) -> None:
    value = {
        "$schema": RESULT_SCHEMA,
        "schema_version": 1,
        "status": status,
        "revision": revision,
    }
    if error is not None:
        value["error"] = error
    print(json.dumps(value, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    args = parser.parse_args()
    try:
        verify_candidate(Path.cwd(), args.revision)
    except (CandidateError, OSError) as exc:
        _emit("failed", args.revision, str(exc))
        return 1
    _emit("verified", args.revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
