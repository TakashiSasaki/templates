#!/usr/bin/env python3
"""Validate translation surface declarations and project reader entries."""

from __future__ import annotations

from typing import Any

ALLOWED_SURFACES = {"reader", "guided"}
ENTRY_V1_KEYS = {"canonical", "language", "translation", "canonical_blob_sha"}
ENTRY_V2_KEYS = ENTRY_V1_KEYS | {"surfaces"}


class TranslationManifestSurfaceError(RuntimeError):
    """Raised when a translation manifest surface declaration is malformed."""


def _surfaces(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TranslationManifestSurfaceError(f"{field} must be a non-empty array")
    result: list[str] = []
    for index, surface in enumerate(value):
        if not isinstance(surface, str) or surface not in ALLOWED_SURFACES:
            raise TranslationManifestSurfaceError(
                f"{field}[{index}] must be one of reader or guided"
            )
        if surface in result:
            raise TranslationManifestSurfaceError(
                f"{field} must not contain duplicate surfaces"
            )
        result.append(surface)
    return tuple(result)


def project_reader_manifest(manifest: dict[str, Any], label: str) -> dict[str, Any]:
    """Return the schema-v1 reader projection consumed by the reader publisher.

    Schema v1 is accepted during the provider migration and already represents
    reader-only entries. Schema v2 entries are validated, filtered by `reader`,
    and stripped of their surface declaration before entering the existing
    reader publication implementation.
    """
    expected_top = {"schema_version", "canonical_language", "translations"}
    if set(manifest) != expected_top:
        raise TranslationManifestSurfaceError(f"{label} has unsupported fields")
    version = manifest.get("schema_version")
    if type(version) is not int or version not in {1, 2}:
        raise TranslationManifestSurfaceError(
            f"{label} schema_version must be integer 1 or 2"
        )
    if manifest.get("canonical_language") != "en":
        raise TranslationManifestSurfaceError(
            f"{label} canonical_language must be en"
        )
    entries = manifest.get("translations")
    if not isinstance(entries, list):
        raise TranslationManifestSurfaceError(f"{label} translations must be an array")
    if version == 1:
        return manifest

    projected: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        field = f"{label}.translations[{index}]"
        if not isinstance(entry, dict) or set(entry) != ENTRY_V2_KEYS:
            raise TranslationManifestSurfaceError(
                f"{field} must contain canonical, language, translation, "
                "canonical_blob_sha, and surfaces"
            )
        surfaces = _surfaces(entry["surfaces"], f"{field}.surfaces")
        if "reader" not in surfaces:
            continue
        projected.append({key: entry[key] for key in ENTRY_V1_KEYS})

    return {
        "schema_version": 1,
        "canonical_language": "en",
        "translations": projected,
    }
