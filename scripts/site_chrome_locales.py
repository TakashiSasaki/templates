"""Validate and resolve Site-owned chrome locale data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
SITE_CHROME_LOCALES = Path(__file__).resolve().parents[1] / "assets/site-chrome-locales.json"
READER_FIELDS = {
    "group_label",
    "canonical_status",
    "canonical_link",
    "translation_status",
}
PWA_FRESHNESS_FIELDS = {
    "saved_copy",
    "checking",
    "unverified",
    "update_available",
    "published_changed",
    "reload",
    "offline_unavailable",
}
GLOSSARY_INLINE_FIELDS = {
    "eyebrow",
    "close_definition",
    "open_in_glossary",
    "definition_unavailable",
    "cached_unverified",
    "external_term_prefix",
    "repository_term_prefix",
    "data_unavailable",
    "definition_load_failed",
    "definition_not_found",
}


class SiteChromeLocaleError(RuntimeError):
    """Raised when Site chrome locale data violates its contract."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SiteChromeLocaleError(f"unable to read Site chrome locales {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SiteChromeLocaleError(
                    f"Site chrome locales contain duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise SiteChromeLocaleError(
            f"unable to parse Site chrome locales {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SiteChromeLocaleError("Site chrome locales must be an object")
    return value


def _normalized_strings(
    value: Any,
    *,
    field: str,
    required_fields: set[str],
) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != required_fields:
        raise SiteChromeLocaleError(
            f"{field} must contain " + ", ".join(sorted(required_fields))
        )
    normalized: dict[str, str] = {}
    for key in sorted(required_fields):
        item = value[key]
        if not isinstance(item, str) or not item.strip():
            raise SiteChromeLocaleError(f"{field}.{key} must be a non-empty string")
        normalized[key] = item.strip()
    return normalized


def load_site_chrome_locales(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if set(data) != {"schema_version", "canonical_language", "locales"}:
        raise SiteChromeLocaleError(
            "Site chrome locales must contain schema_version, canonical_language, and locales"
        )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise SiteChromeLocaleError("Site chrome locales schema_version must be integer 1")
    canonical_language = data["canonical_language"]
    if canonical_language != "en":
        raise SiteChromeLocaleError("Site chrome locales canonical_language must be en")
    raw_locales = data["locales"]
    if not isinstance(raw_locales, list) or not raw_locales:
        raise SiteChromeLocaleError("Site chrome locales locales must be a non-empty array")

    locales: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_locales):
        field = f"locales[{index}]"
        if not isinstance(raw, dict) or set(raw) != {
            "language",
            "language_label",
            "translation_reader",
            "pwa_freshness",
            "glossary_inline",
        }:
            raise SiteChromeLocaleError(
                f"{field} must contain language, language_label, translation_reader, pwa_freshness, and glossary_inline"
            )
        language = raw["language"]
        if not isinstance(language, str) or not LANGUAGE_TAG.fullmatch(language):
            raise SiteChromeLocaleError(
                f"{field}.language must be a lowercase language tag"
            )
        if language in locales:
            raise SiteChromeLocaleError(f"duplicate Site chrome locale: {language}")
        language_label = raw["language_label"]
        if not isinstance(language_label, str) or not language_label.strip():
            raise SiteChromeLocaleError(
                f"{field}.language_label must be a non-empty string"
            )
        locales[language] = {
            "language_label": language_label.strip(),
            "translation_reader": _normalized_strings(
                raw["translation_reader"],
                field=f"{field}.translation_reader",
                required_fields=READER_FIELDS,
            ),
            "pwa_freshness": _normalized_strings(
                raw["pwa_freshness"],
                field=f"{field}.pwa_freshness",
                required_fields=PWA_FRESHNESS_FIELDS,
            ),
            "glossary_inline": _normalized_strings(
                raw["glossary_inline"],
                field=f"{field}.glossary_inline",
                required_fields=GLOSSARY_INLINE_FIELDS,
            ),
        }

    if canonical_language not in locales:
        raise SiteChromeLocaleError(
            "Site chrome locales must include the canonical language locale"
        )
    return {
        "schema_version": 1,
        "canonical_language": canonical_language,
        "locales": locales,
    }


def locale_record(model: dict[str, Any], language: str) -> dict[str, Any] | None:
    locales = model["locales"]
    exact = locales.get(language)
    if exact is not None:
        return exact
    primary = language.split("-", 1)[0]
    return locales.get(primary)


def language_label(model: dict[str, Any], language: str) -> str:
    locale = locale_record(model, language)
    return locale["language_label"] if locale is not None else language


def reader_strings(model: dict[str, Any], language: str) -> dict[str, str]:
    locale = locale_record(model, language)
    if locale is None:
        locale = model["locales"][model["canonical_language"]]
    return locale["translation_reader"]


def pwa_freshness_strings(model: dict[str, Any], language: str) -> dict[str, str]:
    locale = locale_record(model, language)
    if locale is None:
        locale = model["locales"][model["canonical_language"]]
    return locale["pwa_freshness"]


def glossary_inline_strings(model: dict[str, Any], language: str) -> dict[str, str]:
    locale = locale_record(model, language)
    if locale is None:
        locale = model["locales"][model["canonical_language"]]
    return locale["glossary_inline"]


def translation_status(model: dict[str, Any], language: str) -> str:
    locale = locale_record(model, language)
    canonical_primary = model["canonical_language"].split("-", 1)[0]
    if locale is not None and language.split("-", 1)[0] != canonical_primary:
        return locale["translation_reader"]["translation_status"]
    return f"{language_label(model, language)} translation · Non-authoritative"
