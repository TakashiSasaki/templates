#!/usr/bin/env python3
"""Project translated relative-link paths back to canonical provider identities."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable, Mapping, Protocol


class TranslationLinkProjectionError(ValueError):
    """Raised when a translated link cannot be mapped to one canonical identity."""


class TranslationEntryLike(Protocol):
    canonical: PurePosixPath
    translation: PurePosixPath


def normalize_provider_relative(
    base: PurePosixPath,
    raw_path: str,
) -> PurePosixPath:
    """Resolve one relative path against a provider-root-relative source directory."""
    parts = list(base.parts)
    for part in PurePosixPath(raw_path).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise TranslationLinkProjectionError(
                    f"translation link escapes the provider root: {raw_path}"
                )
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise TranslationLinkProjectionError(
            f"translation link resolves to the provider root: {raw_path}"
        )
    return PurePosixPath(*parts)


def build_translation_projection(
    entries: Iterable[TranslationEntryLike],
) -> dict[PurePosixPath, PurePosixPath]:
    """Return the unique translation-source -> canonical-source identity map."""
    projection: dict[PurePosixPath, PurePosixPath] = {}
    for entry in entries:
        previous = projection.get(entry.translation)
        if previous is not None and previous != entry.canonical:
            raise TranslationLinkProjectionError(
                "translation source maps ambiguously to canonical provider sources: "
                f"{entry.translation} -> {previous}, {entry.canonical}"
            )
        projection[entry.translation] = entry.canonical
    return projection


def project_translation_target(
    resolved: PurePosixPath,
    raw_path: str,
    projection: Mapping[PurePosixPath, PurePosixPath],
) -> PurePosixPath:
    """Project a translated path to one canonical provider source identity.

    Manifest-declared translations take precedence, including directory links that
    select a translated ``index.md``. When a relative link stays inside a mirrored
    ``translations/<language>/`` tree but its target has no translation entry, the
    mirror prefix is removed to produce a canonical *candidate*. Callers must then
    validate that candidate against their authoritative published document/asset
    map or canonical navigation edge. This preserves untranslated canonical links
    without allowing unknown targets to become authoritative.

    Targets outside the translation tree are already canonical provider identities
    (for example a directly referenced provider asset) and are preserved.
    """
    mapped = projection.get(resolved)
    if mapped is not None:
        return mapped

    if raw_path.endswith("/") or not resolved.suffix:
        mapped_index = projection.get(resolved / "index.md")
        if mapped_index is not None:
            return mapped_index

    if resolved.parts and resolved.parts[0] == "translations":
        if len(resolved.parts) < 3 or not resolved.parts[1]:
            raise TranslationLinkProjectionError(
                f"translation link has no canonical mirror identity: {resolved}"
            )
        canonical_parts = resolved.parts[2:]
        if not canonical_parts:
            raise TranslationLinkProjectionError(
                f"translation link has no canonical mirror identity: {resolved}"
            )
        return PurePosixPath(*canonical_parts)
    return resolved
