#!/usr/bin/env python3
"""Derive reader translation availability from canonical publication state."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.translation_manifest import (
    TranslationManifest,
    TranslationManifestError,
    load_translation_manifest,
)


class TranslationCoverageError(RuntimeError):
    """Raised when translation coverage cannot be derived safely."""


def _optional_manifest(root: Path, publication: str) -> Path | None:
    relative = PurePosixPath("translations/manifest.json")
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise TranslationCoverageError(
            f"unable to resolve {publication} publication root {root}: {exc}"
        ) from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise TranslationCoverageError(
                f"{publication} translation manifest must not traverse a symlink"
            )
        if not current.exists():
            return None
    if not current.is_file():
        raise TranslationCoverageError(
            f"{publication} translation manifest must be a regular file"
        )
    return current


def _load_manifests(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
) -> dict[str, TranslationManifest]:
    manifests: dict[str, TranslationManifest] = {}
    for publication, (root, _, _) in sorted(publications.items()):
        path = _optional_manifest(root, publication)
        if path is None:
            continue
        label = f"{publication} translation manifest"
        try:
            manifests[publication] = load_translation_manifest(
                path,
                label,
                publication_root=root,
            )
        except TranslationManifestError as exc:
            raise TranslationCoverageError(str(exc)) from exc
    return manifests


def build_reader_coverage(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
    included_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return current/stale/missing coverage for declared reader languages.

    A language enters the coverage universe once at least one provider declares a
    `reader` translation in that language. Missing then means that a canonical page
    included in the assembled reader site has no reader declaration for that
    language. This keeps coverage derived from authority metadata instead of a
    separately maintained translation target list.
    """
    manifests = _load_manifests(publications)
    languages = sorted(
        {
            entry.language
            for manifest in manifests.values()
            for entry in manifest.for_surface("reader")
        }
    )

    page_by_key = {
        (page["publication"], page["document"]): page
        for page in included_pages
    }
    canonical_pages: list[tuple[str, str, PurePosixPath, PurePosixPath]] = []
    canonical_keys: set[tuple[str, PurePosixPath]] = set()
    for publication, (_, documents, _) in sorted(publications.items()):
        for document_id, document in sorted(documents.items()):
            page = page_by_key.get((publication, document_id))
            if page is None:
                continue
            source = document["source"]
            destination = page["destination"]
            canonical_pages.append((publication, document_id, source, destination))
            canonical_keys.add((publication, source))

    entries: dict[tuple[str, str, PurePosixPath], Any] = {}
    for publication, manifest in sorted(manifests.items()):
        for entry in manifest.for_surface("reader"):
            if (publication, entry.canonical) not in canonical_keys:
                raise TranslationCoverageError(
                    "reader translation canonical is not included in the assembled site: "
                    f"{publication}:{entry.canonical}"
                )
            entries[(publication, entry.language, entry.canonical)] = entry

    records: list[dict[str, Any]] = []
    summary = {"current": 0, "stale": 0, "missing": 0}
    for language in languages:
        for publication, document_id, source, destination in canonical_pages:
            entry = entries.get((publication, language, source))
            if entry is None:
                status = "missing"
                record: dict[str, Any] = {
                    "publication": publication,
                    "document": document_id,
                    "language": language,
                    "canonical_source": source.as_posix(),
                    "canonical_destination": destination.as_posix(),
                    "status": status,
                }
            else:
                status = entry.freshness
                if status not in {"current", "stale"}:
                    raise TranslationCoverageError(
                        f"translation freshness was not bound: {publication}:{source}"
                    )
                record = {
                    "publication": publication,
                    "document": document_id,
                    "language": language,
                    "canonical_source": source.as_posix(),
                    "canonical_destination": destination.as_posix(),
                    "translation_source": entry.translation.as_posix(),
                    "canonical_blob_sha": entry.canonical_blob_sha,
                    "current_blob_sha": entry.current_blob_sha,
                    "status": status,
                }
            summary[status] += 1
            records.append(record)

    by_language: dict[str, dict[str, int]] = {}
    for language in languages:
        counts = {"current": 0, "stale": 0, "missing": 0}
        for record in records:
            if record["language"] == language:
                counts[record["status"]] += 1
        by_language[language] = counts

    return {
        "schema_version": 1,
        "canonical_language": "en",
        "surface": "reader",
        "languages": languages,
        "summary": summary,
        "by_language": by_language,
        "records": records,
    }


def write_coverage(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink():
        raise TranslationCoverageError("translation coverage output must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
