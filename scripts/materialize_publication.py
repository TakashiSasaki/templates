#!/usr/bin/env python3
"""Materialize Composition-owned publication build products.

This is the conventional provider entrypoint consumed by Site orchestration.
Composition retains all generator, semantic-revision, dependency, and output
semantics.  The entrypoint is therefore runnable from a generic consumer
checkout even when the caller has not preinstalled Composition validation
dependencies.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DEPENDENCY_LOCK = ROOT / "requirements-dev.lock"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def ensure_runtime_dependencies() -> tempfile.TemporaryDirectory[str] | None:
    """Provide provider-owned locked dependencies without caller knowledge.

    Normal Composition CI already installs the reviewed lock, so the common
    path is allocation-free.  Generic publication consumers may intentionally
    know only the conventional materializer entrypoint; in that case install
    the exact provider lock into an isolated temporary target and extend only
    this materializer process's import path.  The caller environment and
    provider checkout remain unmodified.
    """
    if importlib.util.find_spec("jsonschema") is not None:
        return None
    temporary = tempfile.TemporaryDirectory(prefix="composition-publication-deps-")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--requirement",
            str(DEPENDENCY_LOCK),
            "--no-deps",
            "--target",
            temporary.name,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        temporary.cleanup()
        raise RuntimeError(
            "locked Composition publication dependencies could not be prepared"
            + (f": {detail}" if detail else "")
        )
    sys.path.insert(0, temporary.name)
    return temporary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    dependency_target: tempfile.TemporaryDirectory[str] | None = None
    try:
        source_root = args.source_root.resolve(strict=True)
        if source_root != ROOT.resolve(strict=True):
            print(
                "materialize_publication.py: PUBLICATION_ROOT_MISMATCH: "
                "--source-root must identify this exact Composition checkout",
                file=sys.stderr,
            )
            return 1

        dependency_target = ensure_runtime_dependencies()
        import generate_composition_playground_publication as playground
        from composer_core_impl import CompositionError

        semantic_revision = playground.write_directory(ROOT / "generated")
        checked_revision = playground.check_directory(ROOT / "generated")
        if checked_revision != semantic_revision:
            raise CompositionError(
                "INVALID_PLAYGROUND_PUBLICATION",
                "materialized publication revision did not round-trip",
            )
    except (RuntimeError, OSError, UnicodeError) as exc:
        code = getattr(exc, "code", "PUBLICATION_MATERIALIZATION_FAILED")
        print(f"materialize_publication.py: {code}: {exc}", file=sys.stderr)
        return 1
    finally:
        if dependency_target is not None:
            dependency_target.cleanup()
    print(f"materialized Composition publication assets for {semantic_revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
