#!/usr/bin/env python3
"""Load and validate the canonical schema-v2 translation manifest contract."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

LANGUAGE = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
BLOB_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
ALLOWED_SURFACES = frozenset({"reader", "guided"})
ENTRY_KEYS = frozenset(
    {"canonical", "language", "translation", "canonical_blob_sha", "surfaces"}
)
TOP_LEVEL_KEYS = frozenset({"schema_version", "canonical_language", "translations"})


class TranslationManifestError(RuntimeError):
    """Raised when translation synchronization metadata is malformed or unsafe."""


@dataclass(frozen=True)
class TranslationEntry:
    index: int
    canonical: PurePosixPath
    language: str
    translation: PurePosixPath
    canonical_blob_sha: str
    surfaces: tuple[str, ...]

    def supports(self, surface: str) -> bool:
        return surface in self.surfaces


@dataclass(frozen=True)
class TranslationManifest:
    canonical_language: str
    entries: tuple[TranslationEntry, ...]

    def for_surface(self, surface: str) -> tuple[TranslationEntry, ...]:
        if surface not in ALLOWED_SURFACES:
            raise TranslationManifestError(f"unsupported translation surface: {surface}")
        return tuple(entry for entry in self.entries if entry.supports(surface))


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationManifestError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TranslationManifestError(f"{label} contains duplicate member: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise TranslationManifestError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TranslationManifestError(f"{label} must be an object")
    return value


def _safe_markdown_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise TranslationManifestError(f"{field} must be a safe relative POSIX Markdown path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise TranslationManifestError(f"{field} must be a safe relative POSIX Markdown path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.lower() != ".md":
        raise TranslationManifestError(f"{field} must be a safe relative POSIX Markdown path")
    return path


def _surfaces(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TranslationManifestError(f"{field} must be a non-empty array")
    result: list[str] = []
    for index, surface in enumerate(value):
        if not isinstance(surface, str) or surface not in ALLOWED_SURFACES:
            raise TranslationManifestError(
                f"{field}[{index}] must be one of reader or guided"
            )
        if surface in result:
            raise TranslationManifestError(f"{field} must not contain duplicate surfaces")
        result.append(surface)
    return tuple(result)


def load_translation_manifest(path: Path, label: str) -> TranslationManifest:
    """Load one provider-owned translation manifest using schema version 2 only."""
    data = _read_json(path, label)
    if set(data) != TOP_LEVEL_KEYS:
        raise TranslationManifestError(f"{label} has unsupported fields")
    version = data.get("schema_version")
    if type(version) is not int or version != 2:
        raise TranslationManifestError(f"{label} schema_version must be integer 2")
    canonical_language = data.get("canonical_language")
    if canonical_language != "en":
        raise TranslationManifestError(f"{label} canonical_language must be en")
    raw_entries = data.get("translations")
    if not isinstance(raw_entries, list):
        raise TranslationManifestError(f"{label} translations must be an array")

    entries: list[TranslationEntry] = []
    seen_pairs: set[tuple[str, PurePosixPath]] = set()
    seen_paths: set[PurePosixPath] = set()
    for index, raw in enumerate(raw_entries):
        field = f"{label}.translations[{index}]"
        if not isinstance(raw, dict) or set(raw) != ENTRY_KEYS:
            raise TranslationManifestError(
                f"{field} must contain canonical, language, translation, "
                "canonical_blob_sha, and surfaces"
            )
        canonical = _safe_markdown_path(raw["canonical"], f"{field}.canonical")
        translation = _safe_markdown_path(raw["translation"], f"{field}.translation")
        language = raw["language"]
        blob_sha = raw["canonical_blob_sha"]
        if (
            not isinstance(language, str)
            or not LANGUAGE.fullmatch(language)
            or language == canonical_language
        ):
            raise TranslationManifestError(
                f"{field}.language must be a non-English lowercase language tag"
            )
        if not isinstance(blob_sha, str) or not BLOB_SHA.fullmatch(blob_sha):
            raise TranslationManifestError(
                f"{field}.canonical_blob_sha must be a full lowercase Git blob SHA"
            )
        declared_surfaces = _surfaces(raw["surfaces"], f"{field}.surfaces")
        expected_translation = PurePosixPath("translations") / language / canonical
        if translation != expected_translation:
            raise TranslationManifestError(
                f"{field}.translation must mirror canonical at {expected_translation}"
            )

        pair = (language, canonical)
        if pair in seen_pairs:
            raise TranslationManifestError(
                f"duplicate translation pair: {language} {canonical}"
            )
        if translation in seen_paths:
            raise TranslationManifestError(f"duplicate translation path: {translation}")
        seen_pairs.add(pair)
        seen_paths.add(translation)
        entries.append(
            TranslationEntry(
                index=index,
                canonical=canonical,
                language=language,
                translation=translation,
                canonical_blob_sha=blob_sha,
                surfaces=declared_surfaces,
            )
        )

    return TranslationManifest(
        canonical_language=canonical_language,
        entries=tuple(entries),
    )
