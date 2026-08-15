#!/usr/bin/env python3
"""Build deterministic inline-annotation matches from an integrated glossary model."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Iterator


class GlossaryAnnotationError(RuntimeError):
    """Raised when integrated glossary data cannot form an annotation index."""


@dataclass(frozen=True)
class AnnotationLabel:
    """One unambiguous normalized label mapped to a stable glossary term ID."""

    normalized: str
    term_id: str


@dataclass(frozen=True)
class AnnotationMatch:
    """A non-overlapping source-text span resolved to one glossary concept."""

    start: int
    end: int
    term_id: str


@dataclass(frozen=True)
class AnnotationIndex:
    """Derived matching data; canonical glossary data remains the source of truth."""

    labels: tuple[AnnotationLabel, ...]
    ambiguous: dict[str, tuple[str, ...]]


def normalize_label(value: str) -> str:
    """Use the glossary label identity normalization: NFC followed by case-folding."""
    if not isinstance(value, str) or not value:
        raise GlossaryAnnotationError("annotation labels must be non-empty strings")
    return unicodedata.normalize("NFC", value).casefold()


def _ascii_word(char: str) -> bool:
    return char == "_" or "a" <= char <= "z" or "0" <= char <= "9"


def _label_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise GlossaryAnnotationError(f"{field} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise GlossaryAnnotationError(
                f"{field}[{index}] must be a non-empty string"
            )
        result.append(item)
    return result


def _term_labels(term: dict[str, Any], field: str) -> list[str]:
    preferred = term.get("term")
    if not isinstance(preferred, str) or not preferred:
        raise GlossaryAnnotationError(f"{field}.term must be a non-empty string")
    labels = [preferred, *_label_list(term.get("aliases", []), f"{field}.aliases")]

    localized_labels = term.get("localized_labels", {})
    if not isinstance(localized_labels, dict):
        raise GlossaryAnnotationError(f"{field}.localized_labels must be an object")
    for language, localized in localized_labels.items():
        localized_field = f"{field}.localized_labels.{language}"
        if not isinstance(localized, dict):
            raise GlossaryAnnotationError(f"{localized_field} must be an object")
        localized_term = localized.get("term")
        if not isinstance(localized_term, str) or not localized_term:
            raise GlossaryAnnotationError(
                f"{localized_field}.term must be a non-empty string"
            )
        labels.append(localized_term)
        labels.extend(
            _label_list(localized.get("aliases", []), f"{localized_field}.aliases")
        )
    return labels


def build_annotation_index(model: dict[str, Any]) -> AnnotationIndex:
    """Derive all safely auto-resolvable labels from an integrated glossary model.

    A normalized label shared by multiple term IDs is deliberately omitted from
    automatic matching and reported through ``ambiguous`` instead. Multiple raw
    labels that normalize to the same value for the same term remain safe.
    """
    if not isinstance(model, dict) or not isinstance(model.get("terms"), list):
        raise GlossaryAnnotationError("integrated glossary model must contain terms")

    owners: dict[str, set[str]] = {}
    for index, raw_term in enumerate(model["terms"]):
        field = f"terms[{index}]"
        if not isinstance(raw_term, dict):
            raise GlossaryAnnotationError(f"{field} must be an object")
        term_id = raw_term.get("id")
        if not isinstance(term_id, str) or not term_id:
            raise GlossaryAnnotationError(f"{field}.id must be a non-empty string")
        for label in _term_labels(raw_term, field):
            normalized = normalize_label(label)
            owners.setdefault(normalized, set()).add(term_id)

    ambiguous = {
        label: tuple(sorted(term_ids))
        for label, term_ids in owners.items()
        if len(term_ids) > 1
    }
    labels = tuple(
        sorted(
            (
                AnnotationLabel(normalized=label, term_id=next(iter(term_ids)))
                for label, term_ids in owners.items()
                if len(term_ids) == 1
            ),
            key=lambda item: (-len(item.normalized), item.normalized, item.term_id),
        )
    )
    return AnnotationIndex(labels=labels, ambiguous=ambiguous)


def _normalization_segments(text: str) -> Iterator[tuple[int, int]]:
    """Yield source spans that can be NFC-normalized independently.

    Canonical combining sequences stay together. A class-zero character is also
    retained when NFC composes it with the preceding segment, covering Hangul
    Jamo composition without requiring a second normalization pass over prefixes.
    Each source character is consumed once; composition probes are bounded by the
    current normalization segment rather than by the full text prefix.
    """
    start = 0
    length = len(text)
    while start < length:
        end = start + 1
        while end < length:
            char = text[end]
            if unicodedata.combining(char) != 0:
                end += 1
                continue
            segment = text[start:end]
            if unicodedata.normalize("NFC", segment + char) != (
                unicodedata.normalize("NFC", segment)
                + unicodedata.normalize("NFC", char)
            ):
                end += 1
                continue
            break
        yield start, end
        start = end


def _normalized_boundaries(text: str) -> tuple[str, dict[int, int], dict[int, int]]:
    """Return normalized text plus exact normalized-to-source boundary maps."""
    normalized_parts: list[str] = []
    first_boundary: dict[int, int] = {0: 0}
    last_boundary: dict[int, int] = {0: 0}
    normalized_offset = 0

    for source_start, source_end in _normalization_segments(text):
        part = unicodedata.normalize("NFC", text[source_start:source_end]).casefold()
        first_boundary.setdefault(normalized_offset, source_start)
        last_boundary[normalized_offset] = source_start
        normalized_parts.append(part)
        normalized_offset += len(part)
        first_boundary.setdefault(normalized_offset, source_end)
        last_boundary[normalized_offset] = source_end

    normalized = "".join(normalized_parts)
    expected = unicodedata.normalize("NFC", text).casefold()
    if normalized != expected:
        raise GlossaryAnnotationError(
            "unable to preserve source boundaries during Unicode normalization"
        )
    return normalized, first_boundary, last_boundary


def _source_ascii_word(char: str) -> bool:
    folded = unicodedata.normalize("NFC", char).casefold()
    return bool(folded) and _ascii_word(folded[0])


def _has_valid_boundaries(text: str, start: int, end: int, label: AnnotationLabel) -> bool:
    if not label.normalized:
        return True
    if _ascii_word(label.normalized[0]):
        if start > 0 and _source_ascii_word(text[start - 1]):
            return False
    if _ascii_word(label.normalized[-1]):
        if end < len(text) and _source_ascii_word(text[end]):
            return False
    return True


def find_annotation_matches(text: str, index: AnnotationIndex) -> list[AnnotationMatch]:
    """Return deterministic non-overlapping matches using longest-match-first.

    ASCII word boundaries are enforced independently on whichever side of a
    label begins or ends with an ASCII word character. Non-ASCII labels do not
    require whitespace boundaries, allowing Japanese labels to match ordinary
    Japanese prose.
    """
    if not isinstance(text, str):
        raise GlossaryAnnotationError("annotation source text must be a string")
    if not text or not index.labels:
        return []

    normalized, start_boundaries, end_boundaries = _normalized_boundaries(text)
    by_initial: dict[str, list[AnnotationLabel]] = {}
    for label in index.labels:
        if label.normalized:
            by_initial.setdefault(label.normalized[0], []).append(label)

    matches: list[AnnotationMatch] = []
    cursor = 0
    while cursor < len(normalized):
        matched = False
        for label in by_initial.get(normalized[cursor], []):
            end = cursor + len(label.normalized)
            if end > len(normalized) or normalized[cursor:end] != label.normalized:
                continue
            source_start = start_boundaries.get(cursor)
            source_end = end_boundaries.get(end)
            if source_start is None or source_end is None or source_start >= source_end:
                continue
            if not _has_valid_boundaries(text, source_start, source_end, label):
                continue
            matches.append(
                AnnotationMatch(
                    start=source_start,
                    end=source_end,
                    term_id=label.term_id,
                )
            )
            cursor = end
            matched = True
            break
        if not matched:
            cursor += 1
    return matches
