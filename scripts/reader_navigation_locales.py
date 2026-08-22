#!/usr/bin/env python3
"""Validate reader-navigation locale labels and build current localized route data."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from scripts.publish_translations import TranslationRecord

LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
LABEL_ID = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class ReaderNavigationLocaleError(RuntimeError):
    """Raised when reader-navigation localization data violates its contract."""


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReaderNavigationLocaleError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReaderNavigationLocaleError(
                    f"{label} contains duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise ReaderNavigationLocaleError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReaderNavigationLocaleError(f"{label} must be an object")
    return value


def navigation_titles(nodes: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for node in nodes:
        title = node.get("title")
        if not isinstance(title, str) or not title:
            raise ReaderNavigationLocaleError("canonical navigation contains an invalid title")
        result.add(title)
        children = node.get("children")
        if children is not None:
            if not isinstance(children, list):
                raise ReaderNavigationLocaleError(
                    f"canonical navigation children must be an array: {title}"
                )
            result.update(navigation_titles(children))
    return result


def load_overlays(
    path: Path,
    navigation: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    data = read_json(path, "reader navigation locale overlay")
    if set(data) != {"schema_version", "canonical_language", "locales"}:
        raise ReaderNavigationLocaleError(
            "reader navigation locale overlay has unsupported fields"
        )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ReaderNavigationLocaleError(
            "reader navigation locale overlay schema_version must be integer 1"
        )
    if data["canonical_language"] != "en":
        raise ReaderNavigationLocaleError(
            "reader navigation locale overlay canonical_language must be en"
        )
    locales = data["locales"]
    if not isinstance(locales, list) or not locales:
        raise ReaderNavigationLocaleError(
            "reader navigation locale overlay locales must be a non-empty array"
        )

    expected_titles = navigation_titles(navigation)
    result: dict[str, dict[str, str]] = {}
    for locale_index, locale in enumerate(locales):
        field = f"locales[{locale_index}]"
        if not isinstance(locale, dict) or set(locale) != {"language", "labels"}:
            raise ReaderNavigationLocaleError(
                f"{field} must contain language and labels"
            )
        language = locale["language"]
        if (
            not isinstance(language, str)
            or not LANGUAGE_TAG.fullmatch(language)
            or language == "en"
        ):
            raise ReaderNavigationLocaleError(
                f"{field}.language must be a non-English lowercase language tag"
            )
        if language in result:
            raise ReaderNavigationLocaleError(f"duplicate reader navigation locale: {language}")
        labels = locale["labels"]
        if not isinstance(labels, list) or not labels:
            raise ReaderNavigationLocaleError(f"{field}.labels must be a non-empty array")

        ids: set[str] = set()
        canonical_labels: dict[str, str] = {}
        for label_index, label in enumerate(labels):
            label_field = f"{field}.labels[{label_index}]"
            if (
                not isinstance(label, dict)
                or set(label) != {"id", "canonical", "localized"}
            ):
                raise ReaderNavigationLocaleError(
                    f"{label_field} must contain id, canonical, and localized"
                )
            identifier = label["id"]
            canonical = label["canonical"]
            localized = label["localized"]
            if not isinstance(identifier, str) or not LABEL_ID.fullmatch(identifier):
                raise ReaderNavigationLocaleError(
                    f"{label_field}.id must be lowercase kebab-case"
                )
            if identifier in ids:
                raise ReaderNavigationLocaleError(
                    f"{field}.labels contains duplicate id: {identifier}"
                )
            ids.add(identifier)
            if not isinstance(canonical, str) or not canonical:
                raise ReaderNavigationLocaleError(
                    f"{label_field}.canonical must be a non-empty string"
                )
            if canonical in canonical_labels:
                raise ReaderNavigationLocaleError(
                    f"{field}.labels contains duplicate canonical label: {canonical}"
                )
            if not isinstance(localized, str) or not localized.strip():
                raise ReaderNavigationLocaleError(
                    f"{label_field}.localized must be a non-empty string"
                )
            canonical_labels[canonical] = localized.strip()

        actual_titles = set(canonical_labels)
        if actual_titles != expected_titles:
            missing = sorted(expected_titles - actual_titles)
            extra = sorted(actual_titles - expected_titles)
            detail = []
            if missing:
                detail.append("missing: " + ", ".join(missing))
            if extra:
                detail.append("extra: " + ", ".join(extra))
            raise ReaderNavigationLocaleError(
                f"{field}.labels must exactly cover canonical navigation titles ("
                + "; ".join(detail)
                + ")"
            )
        result[language] = canonical_labels
    return result


def markdown_route(destination: PurePosixPath) -> str:
    if destination.name == "index.md":
        parent = destination.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return f"/{destination.with_suffix('').as_posix()}/"


def build_runtime_map(
    overlays: dict[str, dict[str, str]],
    records: Iterable[TranslationRecord],
) -> dict[str, Any]:
    routes: dict[str, dict[str, str]] = {language: {} for language in overlays}
    for record in records:
        language_routes = routes.get(record.language)
        if language_routes is None:
            continue
        canonical_route = markdown_route(record.canonical_destination)
        translated_route = markdown_route(record.translation_destination)
        existing = language_routes.setdefault(canonical_route, translated_route)
        if existing != translated_route:
            raise ReaderNavigationLocaleError(
                f"conflicting localized route for {record.language}:{canonical_route}"
            )

    return {
        "schema_version": 1,
        "canonical_language": "en",
        "locales": [
            {
                "language": language,
                "labels": overlays[language],
                "routes": routes[language],
            }
            for language in sorted(overlays)
        ],
    }


def write_runtime_map(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
