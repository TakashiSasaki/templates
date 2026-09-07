#!/usr/bin/env python3
"""Stable schema-v3 CLI entrypoint for Site publication assembly."""

from __future__ import annotations

import argparse
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

__all__ = ["AssemblyError", "load_catalog", "main"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", action="append", default=[])
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    try:
        publication_roots = parse_publications(args.publication)
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
