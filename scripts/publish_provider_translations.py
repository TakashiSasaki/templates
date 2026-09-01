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
from scripts.reader_navigation_locales import (
    ReaderNavigationLocaleError,
    build_runtime_map,
    load_overlays,
    write_runtime_map,
)
from scripts.translation_coverage import (
    TranslationCoverageError,
    build_reader_coverage,
    write_coverage,
)
from scripts.translation_fragment_reconciliation import (
    TranslationFragmentReconciliationError,
    reconcile_translation_fragments,
)
from scripts.translation_link_selection import rewrite_current_localized_links
from scripts.translation_reader_metadata import exclude_translation_from_search


SITE_SOURCE_ROOT = Path(__file__).resolve().parents[1]
READER_NAVIGATION_LOCALES = SITE_SOURCE_ROOT / "reader-navigation-locales.json"


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
    parser.add_argument(
        "--reader-navigation-locales",
        type=Path,
        default=READER_NAVIGATION_LOCALES,
    )
    args = parser.parse_args()

    try:
        roots = parse_publications(args.publication)
        publications = {}
        for name, root in sorted(roots.items()):
            resolved = root.resolve(strict=True)
            documents, assets = load_catalog(name, resolved)
            publications[name] = (resolved, documents, assets)

        _, navigation = load_manifest(args.site_root / "site-manifest.json")
        overlays = load_overlays(args.reader_navigation_locales, navigation)
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
            skip_stale=True,
        )
        reconciled_fragment_count = reconcile_translation_fragments(
            publications,
            included_pages,
            records,
            docs_root,
        )
        localized_link_count = rewrite_current_localized_links(records, docs_root)
        for record in records:
            exclude_translation_from_search(
                docs_root.joinpath(*record.translation_destination.parts)
            )
        write_publication_map(
            args.output_root / "translation-publication.json",
            records,
        )
        write_runtime_map(
            docs_root / "reader-navigation-runtime.json",
            build_runtime_map(overlays, records),
        )
        coverage = build_reader_coverage(publications, included_pages)
        write_coverage(
            args.output_root / "translation-coverage.json",
            coverage,
        )
        print(f"translations published: {len(records)}")
        print(f"canonical translation fragments reconciled: {reconciled_fragment_count}")
        print(f"localized reader links selected: {localized_link_count}")
        print(
            "reader navigation locales: "
            + ", ".join(sorted(overlays))
        )
        print(
            "reader translation coverage: "
            f"current={coverage['summary']['current']} "
            f"stale={coverage['summary']['stale']} "
            f"missing={coverage['summary']['missing']}"
        )
    except (
        OSError,
        ReaderNavigationLocaleError,
        TranslationCoverageError,
        TranslationFragmentReconciliationError,
        translation_publisher.TranslationPublicationError,
        RuntimeError,
    ) as exc:
        print(f"publish_provider_translations.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
