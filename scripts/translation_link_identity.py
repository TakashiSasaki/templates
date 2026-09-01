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
    """Project a resolved translated path to its canonical provider source identity.

    A target inside ``translations/`` is never inferred by mirroring path text. It
    must be declared by the translation manifest. Targets outside that tree are
    already canonical provider identities (for example a directly referenced
    provider asset) and are preserved for the caller's publication mapping.
    """
    mapped = projection.get(resolved)
    if mapped is not None:
        return mapped

    if raw_path.endswith("/") or not resolved.suffix:
        mapped_index = projection.get(resolved / "index.md")
        if mapped_index is not None:
            return mapped_index

    if resolved.parts and resolved.parts[0] == "translations":
        raise TranslationLinkProjectionError(
            "translation link resolves inside the translation tree without a "
            f"manifest mapping: {resolved}"
        )
    return resolved
