#!/usr/bin/env python3
"""Publish provider-declared translations into an assembled documentation tree."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from assemble_publications import load_catalog, load_manifest, pages, parse_publications
from publish_translations import TranslationPublicationError, publish_translations
from translation_reader_metadata import exclude_translation_from_search


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", action="append", default=[])
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    try:
        roots = parse_publications(args.publication)
        publications = {}
        for name, root in sorted(roots.items()):
            resolved = root.resolve(strict=True)
            documents, assets = load_catalog(name, resolved)
            publications[name] = (resolved, documents, assets)

        _, navigation = load_manifest(args.site_root / "site-manifest.json")
        docs_root = args.output_root / "docs"
        included_pages = [
            page
            for page in pages(navigation)
            if docs_root.joinpath(*page["destination"].parts).is_file()
        ]
        records = publish_translations(publications, included_pages, docs_root)
        for record in records:
            exclude_translation_from_search(
                docs_root.joinpath(*record.translation_destination.parts)
            )
        print(f"translations published: {len(records)}")
    except (OSError, TranslationPublicationError, RuntimeError) as exc:
        print(f"publish_provider_translations.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
