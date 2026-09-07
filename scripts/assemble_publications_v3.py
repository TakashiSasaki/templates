#!/usr/bin/env python3
"""Stable schema-v3 CLI entrypoint for Site publication assembly."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.assemble_publications import (
    AssemblyError,
    assemble,
    load_catalog,
    parse_publications,
)
from scripts.publication_link_rewriter import rebase_publication_links

__all__ = ["AssemblyError", "load_catalog", "main", "materialize_provider_publication_assets"]


PLAYGROUND_PUBLICATION_MANIFEST = Path("generated/composition-playground-publication.json")
PLAYGROUND_PUBLICATION_GENERATOR = Path("scripts/generate_composition_playground_publication.py")


def materialize_provider_publication_assets(publication_roots: dict[str, Path]) -> None:
    """Ask a pinned provider to materialize its own declared build products.

    Site owns only orchestration here.  The generator, semantic revision manifest,
    resolver behavior, and publication bytes remain entirely Composition-owned.
    """
    composition_root = publication_roots.get("composition")
    if composition_root is None:
        return
    root = composition_root.resolve(strict=True)
    manifest = root / PLAYGROUND_PUBLICATION_MANIFEST
    if not manifest.is_file():
        return
    generator = root / PLAYGROUND_PUBLICATION_GENERATOR
    if not generator.is_file():
        raise AssemblyError(
            "Composition declares Playground publication build products but has no provider generator"
        )
    result = subprocess.run(
        [sys.executable, str(generator), "--output-dir", str(manifest.parent)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AssemblyError(
            "Composition Playground publication materialization failed"
            + (f": {detail}" if detail else "")
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", action="append", default=[])
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    try:
        publication_roots = parse_publications(args.publication)
        materialize_provider_publication_assets(publication_roots)
        summary = assemble(publication_roots, args.site_root, args.output_root)
        rebased = rebase_publication_links(
            publication_roots,
            args.site_root,
            args.output_root,
        )
        summary.append(f"publication links rebased: {rebased}")
        print("\n".join(summary))
    except (AssemblyError, OSError, UnicodeError) as exc:
        print(f"assemble_publications_v3.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
