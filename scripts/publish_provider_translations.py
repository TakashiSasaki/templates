#!/usr/bin/env python3
"""Publish provider-declared translations into an assembled documentation tree."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import publish_translations as translation_publisher
from scripts.assemble_publications import load_manifest, pages, parse_publications
from scripts.assemble_publications_v3 import load_catalog
from scripts.translation_reader_metadata import exclude_translation_from_search


def write_publication_map(
    path: Path,
    records: list[translation_publisher.TranslationRecord],
) -> None:
    translations = []
    for record in records:
        translations.append(
            {
                "publication": record.publication,
                "language": record.language,
                "canonical_destination": record.canonical_destination.as_posix(),
                "translation_destination": record.translation_destination.as_posix(),
            }
        )
    payload = {
        "schema_version": 1,
        "canonical_language": "en",
        "translations": translations,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
        records = translation_publisher.publish_translations(
            publications,
            included_pages,
            docs_root,
        )
        for record in records:
            exclude_translation_from_search(
                docs_root.joinpath(*record.translation_destination.parts)
            )
        write_publication_map(
            args.output_root / "translation-publication.json",
            records,
        )
        print(f"translations published: {len(records)}")
    except (
        OSError,
        translation_publisher.TranslationPublicationError,
        RuntimeError,
    ) as exc:
        print(f"publish_provider_translations.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
