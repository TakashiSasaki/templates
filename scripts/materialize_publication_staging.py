#!/usr/bin/env python3
"""Materialize an explicit Site-owned publication mapping for compatibility builds."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.assemble_publications import AssemblyError, load_manifest, parse_name, safe_path
from scripts.prepare_repository_tree_publication import PreparationError, augment_manifest
from scripts.reader_navigation_locales import (
    LABEL_ID,
    LANGUAGE_TAG,
    ReaderNavigationLocaleError,
    load_overlays,
    navigation_titles,
)


class PublicationStagingError(RuntimeError):
    """Raised when a staged publication mapping is unsafe or inconsistent."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PublicationStagingError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PublicationStagingError(f"{label} contains duplicate member: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise PublicationStagingError(
            f"{label} contains non-standard numeric constant: {value}"
        )

    try:
        value = json.loads(
            text,
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise PublicationStagingError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationStagingError(f"{label} must be an object")
    return value


def _name(value: Any, field: str) -> str:
    try:
        return parse_name(value, field)
    except AssemblyError as exc:
        raise PublicationStagingError(str(exc)) from exc


def _destination(value: Any, field: str) -> str:
    try:
        path = safe_path(value, field)
    except AssemblyError as exc:
        raise PublicationStagingError(str(exc)) from exc
    if path.suffix.lower() != ".md":
        raise PublicationStagingError(f"{field} must be a Markdown destination")
    return path.as_posix()


def _walk_pages(
    nodes: list[dict[str, Any]],
) -> Iterator[tuple[list[dict[str, Any]], int, dict[str, Any]]]:
    for index, node in enumerate(nodes):
        children = node.get("children")
        if isinstance(children, list):
            yield from _walk_pages(children)
        elif "publication" in node:
            yield nodes, index, node


def _load_staging(path: Path, staging_id: str) -> dict[str, Any]:
    data = _read_json(path, "publication staging contract")
    schema_version = data.get("schema_version")
    if (
        set(data) != {"schema_version", "mappings"}
        or type(schema_version) is not int
        or schema_version != 1
    ):
        raise PublicationStagingError(
            "publication staging contract must be integer schema version 1 with mappings"
        )
    mappings = data["mappings"]
    if not isinstance(mappings, list) or not mappings:
        raise PublicationStagingError("publication staging mappings must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(mappings):
        field = f"mappings[{index}]"
        if not isinstance(raw, dict) or set(raw) != {
            "id",
            "publication",
            "document",
            "title",
            "destination",
            "insert_after",
            "localizations",
        }:
            raise PublicationStagingError(
                f"{field} must contain id, publication, document, title, destination, "
                "insert_after, and localizations"
            )
        identifier = _name(raw["id"], f"{field}.id")
        if identifier in ids:
            raise PublicationStagingError(f"duplicate publication staging id: {identifier}")
        ids.add(identifier)
        publication = _name(raw["publication"], f"{field}.publication")
        if publication not in {"composition", "policy"}:
            raise PublicationStagingError(
                f"{field}.publication must be composition or policy"
            )
        document = _name(raw["document"], f"{field}.document")
        title = raw["title"]
        if not isinstance(title, str) or not title.strip() or title != title.strip():
            raise PublicationStagingError(f"{field}.title must be a trimmed non-empty string")
        destination = _destination(raw["destination"], f"{field}.destination")

        anchor = raw["insert_after"]
        if not isinstance(anchor, dict) or set(anchor) != {"publication", "document"}:
            raise PublicationStagingError(
                f"{field}.insert_after must identify publication and document"
            )
        insert_after = {
            "publication": _name(
                anchor["publication"], f"{field}.insert_after.publication"
            ),
            "document": _name(anchor["document"], f"{field}.insert_after.document"),
        }

        localizations = raw["localizations"]
        if not isinstance(localizations, list):
            raise PublicationStagingError(f"{field}.localizations must be an array")
        normalized_localizations: list[dict[str, str]] = []
        languages: set[str] = set()
        for locale_index, locale in enumerate(localizations):
            locale_field = f"{field}.localizations[{locale_index}]"
            if not isinstance(locale, dict) or set(locale) != {
                "language",
                "label_id",
                "localized",
            }:
                raise PublicationStagingError(
                    f"{locale_field} must contain language, label_id, and localized"
                )
            language = locale["language"]
            label_id = locale["label_id"]
            localized = locale["localized"]
            if (
                not isinstance(language, str)
                or not LANGUAGE_TAG.fullmatch(language)
                or language == "en"
            ):
                raise PublicationStagingError(
                    f"{locale_field}.language must be a non-English lowercase language tag"
                )
            if language in languages:
                raise PublicationStagingError(
                    f"{field}.localizations contains duplicate language: {language}"
                )
            languages.add(language)
            if not isinstance(label_id, str) or not LABEL_ID.fullmatch(label_id):
                raise PublicationStagingError(
                    f"{locale_field}.label_id must be lowercase kebab-case"
                )
            if (
                not isinstance(localized, str)
                or not localized.strip()
                or localized != localized.strip()
            ):
                raise PublicationStagingError(
                    f"{locale_field}.localized must be a trimmed non-empty string"
                )
            normalized_localizations.append(
                {
                    "language": language,
                    "label_id": label_id,
                    "localized": localized,
                }
            )

        normalized.append(
            {
                "id": identifier,
                "publication": publication,
                "document": document,
                "title": title,
                "destination": destination,
                "insert_after": insert_after,
                "localizations": normalized_localizations,
            }
        )

    matches = [mapping for mapping in normalized if mapping["id"] == staging_id]
    if len(matches) != 1:
        raise PublicationStagingError(f"unknown publication staging id: {staging_id}")
    return matches[0]


def _temporary_json(path: Path, payload: dict[str, Any]) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2))
            stream.write("\n")
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def materialize(site_root: Path, staging_id: str) -> None:
    site_root = site_root.resolve(strict=True)
    staging_path = site_root / "publication-staging.json"
    manifest_path = site_root / "site-manifest.json"
    locales_path = site_root / "reader-navigation-locales.json"

    mapping = _load_staging(staging_path, staging_id)
    manifest = _read_json(manifest_path, "site manifest")
    locales = _read_json(locales_path, "reader navigation locale overlay")

    try:
        load_manifest(manifest_path)
        prepared_navigation = augment_manifest(manifest)["navigation"]
        load_overlays(locales_path, prepared_navigation)
    except (AssemblyError, PreparationError, ReaderNavigationLocaleError) as exc:
        raise PublicationStagingError(
            f"active Site mapping must validate before staging: {exc}"
        ) from exc

    navigation = manifest.get("navigation")
    if not isinstance(navigation, list):
        raise PublicationStagingError("site manifest navigation must be an array")
    existing_pages = list(_walk_pages(navigation))
    target_key = (mapping["publication"], mapping["document"])
    target_matches = [
        node
        for _, _, node in existing_pages
        if (node.get("publication"), node.get("document")) == target_key
    ]
    if target_matches:
        raise PublicationStagingError(
            f"staged document is already active: {mapping['publication']}:{mapping['document']}"
        )
    destination_matches = [
        node for _, _, node in existing_pages if node.get("destination") == mapping["destination"]
    ]
    if destination_matches:
        raise PublicationStagingError(
            f"staged destination is already active: {mapping['destination']}"
        )

    anchor_key = (
        mapping["insert_after"]["publication"],
        mapping["insert_after"]["document"],
    )
    anchor_matches = [
        (parent, index)
        for parent, index, node in existing_pages
        if (node.get("publication"), node.get("document")) == anchor_key
    ]
    if len(anchor_matches) != 1:
        raise PublicationStagingError(
            "staging insertion anchor must match exactly one active page: "
            f"{anchor_key[0]}:{anchor_key[1]}"
        )

    # Locale coverage is defined over prepared navigation, including generated
    # repository-tree titles, rather than only the raw manifest.
    original_titles = navigation_titles(prepared_navigation)
    anchor_parent, anchor_index = anchor_matches[0]
    # anchor_parent is a sublist of manifest["navigation"], so this mutation is
    # intentionally reflected in the manifest serialized below.
    anchor_parent.insert(
        anchor_index + 1,
        {
            "title": mapping["title"],
            "publication": mapping["publication"],
            "document": mapping["document"],
            "destination": mapping["destination"],
        },
    )

    locale_entries = locales.get("locales")
    if not isinstance(locale_entries, list) or not locale_entries:
        raise PublicationStagingError(
            "reader navigation locale overlay locales must be a non-empty array"
        )
    if mapping["title"] in original_titles:
        if mapping["localizations"]:
            raise PublicationStagingError(
                "staging localizations must be empty when the canonical title already exists"
            )
    else:
        configured = {
            locale["language"]: locale for locale in mapping["localizations"]
        }
        active_languages = {
            locale.get("language")
            for locale in locale_entries
            if isinstance(locale, dict)
        }
        if set(configured) != active_languages:
            raise PublicationStagingError(
                "staging localizations must exactly cover active reader locales"
            )
        for locale in locale_entries:
            language = locale["language"]
            labels = locale.get("labels")
            if not isinstance(labels, list):
                raise PublicationStagingError(
                    f"reader locale {language} labels must be an array"
                )
            staged_locale = configured[language]
            labels.append(
                {
                    "id": staged_locale["label_id"],
                    "canonical": mapping["title"],
                    "localized": staged_locale["localized"],
                }
            )

    manifest_temporary = _temporary_json(manifest_path, manifest)
    try:
        locales_temporary = _temporary_json(locales_path, locales)
        try:
            try:
                load_manifest(manifest_temporary)
                staged_manifest = _read_json(
                    manifest_temporary,
                    "materialized site manifest",
                )
                prepared_staged_navigation = augment_manifest(staged_manifest)["navigation"]
                load_overlays(locales_temporary, prepared_staged_navigation)
            except (AssemblyError, PreparationError, ReaderNavigationLocaleError) as exc:
                raise PublicationStagingError(
                    f"materialized Site mapping failed canonical validation: {exc}"
                ) from exc
            # Both files are fully validated before either replacement. A rare
            # failure of the second replacement can leave only this disposable,
            # build-only checkout partially staged; no deployment path consumes it.
            os.replace(manifest_temporary, manifest_path)
            os.replace(locales_temporary, locales_path)
        finally:
            locales_temporary.unlink(missing_ok=True)
    finally:
        manifest_temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--staging-id", required=True)
    args = parser.parse_args()
    try:
        materialize(args.site_root, args.staging_id)
    except (PublicationStagingError, OSError, UnicodeError) as exc:
        print(f"materialize_publication_staging.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())