#!/usr/bin/env python3
"""Build deterministic inline-annotation matches from an integrated glossary model."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


class GlossaryAnnotationError(RuntimeError):
    """Raised when integrated glossary data cannot form an annotation index."""


@dataclass(frozen=True)
class AnnotationLabel:
    """One unambiguous normalized label mapped to a stable glossary term ID."""

    normalized: str
    term_id: str

    @property
    def requires_word_boundaries(self) -> bool:
        return bool(self.normalized) and _ascii_word(self.normalized[0]) and _ascii_word(
            self.normalized[-1]
        )


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


def _term_labels(term: dict[str, Any]) -> list[str]:
    labels = [term["term"], *term.get("aliases", [])]
    for localized in term.get("localized_labels", {}).values():
        labels.append(localized["term"])
        labels.extend(localized.get("aliases", []))
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
        if not isinstance(raw_term, dict):
            raise GlossaryAnnotationError(f"terms[{index}] must be an object")
        term_id = raw_term.get("id")
        preferred = raw_term.get("term")
        if not isinstance(term_id, str) or not term_id:
            raise GlossaryAnnotationError(f"terms[{index}].id must be a non-empty string")
        if not isinstance(preferred, str) or not preferred:
            raise GlossaryAnnotationError(f"terms[{index}].term must be a non-empty string")
        try:
            raw_labels = _term_labels(raw_term)
        except (KeyError, TypeError) as exc:
            raise GlossaryAnnotationError(
                f"terms[{index}] contains invalid localized label data"
            ) from exc
        for label in raw_labels:
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


def _normalized_boundaries(text: str) -> tuple[str, dict[int, int], dict[int, int]]:
    """Return normalized text plus normalized-offset to source-boundary maps.

    Most site text is already NFC and case-folding preserves length, so the fast
    path is linear. The slower prefix map is only needed for uncommon expansion
    or composition cases such as German sharp-s or decomposed accents.
    """
    normalized = unicodedata.normalize("NFC", text).casefold()
    if len(normalized) == len(text):
        direct = {index: index for index in range(len(text) + 1)}
        return normalized, direct, direct

    first_boundary: dict[int, int] = {}
    last_boundary: dict[int, int] = {}
    for source_offset in range(len(text) + 1):
        normalized_offset = len(
            unicodedata.normalize("NFC", text[:source_offset]).casefold()
        )
        first_boundary.setdefault(normalized_offset, source_offset)
        last_boundary[normalized_offset] = source_offset
    return normalized, first_boundary, last_boundary


def _has_valid_boundaries(text: str, start: int, end: int, label: AnnotationLabel) -> bool:
    if not label.requires_word_boundaries:
        return True
    if start > 0 and _ascii_word(text[start - 1].casefold()[:1]):
        return False
    if end < len(text) and _ascii_word(text[end].casefold()[:1]):
        return False
    return True


def find_annotation_matches(text: str, index: AnnotationIndex) -> list[AnnotationMatch]:
    """Return deterministic non-overlapping matches using longest-match-first.

    Labels that start/end with ASCII word characters require ASCII word
    boundaries. This prevents English identifiers such as ``Branch`` from
    matching inside ``branching`` while allowing Japanese labels to match inside
    ordinary Japanese prose where whitespace is not a lexical boundary.
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
