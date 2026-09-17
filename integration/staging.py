"""Publication staging validation and atomic mapping selection."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterator
from integration.publication_model import AssemblyError, load_manifest, parse_name, safe_path
from integration.reader_navigation_locales import LABEL_ID, LANGUAGE_TAG, ReaderNavigationLocaleError, load_overlays, navigation_titles

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


def _load_staging(path: Path, staging_ids: list[str]) -> list[dict[str, Any]]:
    if not staging_ids:
        raise PublicationStagingError("at least one publication staging id is required")
    if len(set(staging_ids)) != len(staging_ids):
        raise PublicationStagingError("duplicate selected publication staging id")

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

    by_id = {mapping["id"]: mapping for mapping in normalized}
    selected: list[dict[str, Any]] = []
    for staging_id in staging_ids:
        if staging_id not in by_id:
            raise PublicationStagingError(f"unknown publication staging id: {staging_id}")
        selected.append(by_id[staging_id])
    return selected


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def stage_models(site_root: Path, staging_ids: list[str]) -> Path:
    """Return a private staged qualification root; never replace files in site_root."""

    site_root = site_root.resolve(strict=True)
    staging_path = site_root / "publication-staging.json"
    manifest_path = site_root / "site-manifest.json"
    locales_path = site_root / "reader-navigation-locales.json"
    original_manifest = manifest_path.read_bytes()
    original_locales = locales_path.read_bytes()

    mappings = _load_staging(staging_path, staging_ids)
    manifest = _read_json(manifest_path, "site manifest")
    locales = _read_json(locales_path, "reader navigation locale overlay")

    try:
        load_manifest(manifest_path)
        prepared_navigation = manifest["navigation"]
        load_overlays(locales_path, prepared_navigation)
    except (AssemblyError, ReaderNavigationLocaleError) as exc:
        raise PublicationStagingError(
            f"active Site mapping must validate before staging: {exc}"
        ) from exc

    navigation = manifest.get("navigation")
    if isinstance(navigation, dict):
        existing_pages = []
        for aud, audience_tree in navigation.items():
            if isinstance(audience_tree, list):
                for parent, index, node in _walk_pages(audience_tree):
                    existing_pages.append((aud, parent, index, node))
    elif isinstance(navigation, list):
        existing_pages = [("use", parent, index, node) for parent, index, node in _walk_pages(navigation)]
    else:
        raise PublicationStagingError("site manifest navigation must be an object or array")
    existing_keys = {
        (node.get("publication"), node.get("document"))
        for _, _, _, node in existing_pages
    }
    existing_destinations = {node.get("destination") for _, _, _, node in existing_pages}
    selected_keys: set[tuple[str, str]] = set()
    selected_destinations: set[str] = set()
    anchor_operations: dict[
        tuple[str, str], tuple[str, list[dict[str, Any]], int, list[dict[str, Any]]]
    ] = {}
    original_titles = navigation_titles(prepared_navigation)
    selected_titles: set[str] = set()

    for mapping in mappings:
        target_key = (mapping["publication"], mapping["document"])
        if target_key in selected_keys:
            raise PublicationStagingError(
                "duplicate selected staged publication/document key: "
                f"{target_key[0]}:{target_key[1]}"
            )
        selected_keys.add(target_key)
        if target_key in existing_keys:
            raise PublicationStagingError(
                f"staged document is already active: {mapping['publication']}:{mapping['document']}"
            )

        destination = mapping["destination"]
        if destination in selected_destinations:
            raise PublicationStagingError(
                f"duplicate selected staged destination: {destination}"
            )
        selected_destinations.add(destination)
        if destination in existing_destinations:
            raise PublicationStagingError(f"staged destination is already active: {destination}")

        anchor_key = (
            mapping["insert_after"]["publication"],
            mapping["insert_after"]["document"],
        )
        anchor_matches = [
            (aud, parent, index)
            for aud, parent, index, node in existing_pages
            if (node.get("publication"), node.get("document")) == anchor_key
        ]
        if len(anchor_matches) != 1:
            raise PublicationStagingError(
                "staging insertion anchor must match exactly one active page: "
                f"{anchor_key[0]}:{anchor_key[1]}"
            )
        anchor_aud, anchor_parent, anchor_index = anchor_matches[0]
        operation = anchor_operations.setdefault(
            anchor_key, (anchor_aud, anchor_parent, anchor_index, [])
        )
        operation[3].append(mapping)

        title = mapping["title"]
        if title in selected_titles:
            raise PublicationStagingError(f"duplicate staged navigation title: {title}")
        selected_titles.add(title)

    locale_entries = locales.get("locales")
    if not isinstance(locale_entries, list) or not locale_entries:
        raise PublicationStagingError(
            "reader navigation locale overlay locales must be a non-empty array"
        )
    active_languages = {
        locale.get("language") for locale in locale_entries if isinstance(locale, dict)
    }
    existing_label_ids = {
        label.get("id")
        for locale in locale_entries
        if isinstance(locale, dict)
        for label in locale.get("labels", [])
        if isinstance(label, dict)
    }
    selected_label_ids: set[str] = set()
    for mapping in mappings:
        if mapping["title"] in original_titles:
            if mapping["localizations"]:
                raise PublicationStagingError(
                    "staging localizations must be empty when the canonical title already exists"
                )
            continue
        configured = {locale["language"]: locale for locale in mapping["localizations"]}
        if set(configured) != active_languages:
            raise PublicationStagingError(
                "staging localizations must exactly cover active reader locales"
            )
        mapping_label_ids: set[str] = set()
        for locale in mapping["localizations"]:
            label_id = locale["label_id"]
            if (
                label_id in existing_label_ids
                or label_id in selected_label_ids
                or label_id in mapping_label_ids
            ):
                raise PublicationStagingError(f"duplicate staged localization label id: {label_id}")
            mapping_label_ids.add(label_id)
            selected_label_ids.add(label_id)

    for locale in locale_entries:
        language = locale["language"]
        if not isinstance(locale.get("labels"), list):
            raise PublicationStagingError(f"reader locale {language} labels must be an array")

    # Apply all insertions to the in-memory manifest in explicit selection order.
    # Multiple mappings may share an active anchor; their order remains stable.
    for anchor_aud, parent, index, grouped in sorted(
        anchor_operations.values(), key=lambda operation: operation[2], reverse=True
    ):
        parent[index + 1:index + 1] = [
            {
                "title": mapping["title"],
                "publication": mapping["publication"],
                "document": mapping["document"],
                "destination": mapping["destination"],
            }
            for mapping in grouped
        ]

    if manifest.get("schema_version") == 3 and "documents" in manifest:
        for anchor_aud, _, _, grouped in anchor_operations.values():
            for mapping in grouped:
                manifest["documents"].append(
                    {
                        "publication": mapping["publication"],
                        "document": mapping["document"],
                        "title": mapping["title"],
                        "destination": mapping["destination"],
                        "primary_audience": anchor_aud,
                        "additional_audiences": [],
                    }
                )

    for mapping in mappings:
        if mapping["title"] in original_titles:
            continue
        configured = {locale["language"]: locale for locale in mapping["localizations"]}
        for locale in locale_entries:
            staged_locale = configured[locale["language"]]
            locale["labels"].append(
                {
                    "id": staged_locale["label_id"],
                    "canonical": mapping["title"],
                    "localized": staged_locale["localized"],
                }
            )

    return manifest, locales
