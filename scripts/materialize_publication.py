#!/usr/bin/env python3
"""Materialize Composition-owned publication build products.

This is the conventional provider entrypoint consumed by Site orchestration.
Composition retains all generator, semantic-revision, and output semantics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_composition_playground_publication as playground  # noqa: E402
from composer_core_impl import CompositionError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        source_root = args.source_root.resolve(strict=True)
        if source_root != ROOT.resolve(strict=True):
            raise CompositionError(
                "PUBLICATION_ROOT_MISMATCH",
                "--source-root must identify this exact Composition checkout",
            )
        semantic_revision = playground.write_directory(ROOT / "generated")
        checked_revision = playground.check_directory(ROOT / "generated")
        if checked_revision != semantic_revision:
            raise CompositionError(
                "INVALID_PLAYGROUND_PUBLICATION",
                "materialized publication revision did not round-trip",
            )
    except (CompositionError, OSError, UnicodeError) as exc:
        code = getattr(exc, "code", "PUBLICATION_MATERIALIZATION_FAILED")
        print(f"materialize_publication.py: {code}: {exc}", file=sys.stderr)
        return 1
    print(f"materialized Composition publication assets for {semantic_revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
