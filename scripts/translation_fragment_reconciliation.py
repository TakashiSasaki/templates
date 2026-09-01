#!/usr/bin/env python3
"""Reconcile translated cross-page fragments with canonical reader links."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from scripts.translation_link_identity import (
    TranslationLinkProjectionError,
    normalize_provider_relative,
)

INLINE_LINK = re.compile(
    r"(?P<image>!?)\[(?P<label>[^\]\n]*)\]\((?P<target>[^)\n]+)\)"
)
REFERENCE_TARGET = re.compile(
    r"^(?P<prefix>\s{0,3}\[(?!\^)[^\]\n]+\]:\s*)"
    r"(?P<target><[^>\n]+>|\S+)(?P<suffix>.*)$"
)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


class TranslationFragmentReconciliationError(RuntimeError):
    """Raised when translated fragment identity cannot be reconciled safely."""


class TranslationRecordLike(Protocol):
    publication: str
    canonical_source: PurePosixPath
    translation_source: PurePosixPath
    translation_destination: PurePosixPath


def _split_link_target(raw: str) -> tuple[str, str, str]:
    leading = raw[: len(raw) - len(raw.lstrip())]
    stripped = raw.strip()
    if not stripped:
        return leading, "", ""
    if stripped.startswith("<"):
        end = stripped.find(">")
        if end == -1:
            return leading, stripped, ""
        return leading, stripped[1:end], stripped[end + 1 :]
    match = re.match(r"(\S+)(.*)\Z", stripped)
    assert match is not None
    return leading, match.group(1), match.group(2)


def _regular_file(root: Path, relative: PurePosixPath, field: str) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise TranslationFragmentReconciliationError(
                f"{field} escapes its root: {relative}"
            ) from exc
        if current.is_symlink():
            raise TranslationFragmentReconciliationError(
                f"{field} must not traverse a symlink: {relative}"
            )
    if not current.is_file():
        raise TranslationFragmentReconciliationError(
            f"{field} must be an existing regular file: {relative}"
        )
    return current


def _document_destination(
    publication: str,
    source: PurePosixPath,
    raw_path: str,
    canonical_destinations: dict[tuple[str, PurePosixPath], PurePosixPath],
) -> PurePosixPath | None:
    destination = canonical_destinations.get((publication, source))
    if destination is not None:
        return destination
    if raw_path.endswith("/") or not source.suffix:
        return canonical_destinations.get((publication, source / "index.md"))
    return None


def _iter_markdown_targets(text: str):
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue
        if fence_character is not None:
            continue
        for match in INLINE_LINK.finditer(line):
            if not match.group("image"):
                yield match.group("target")
        reference = REFERENCE_TARGET.match(line.rstrip("\r\n"))
        if reference:
            yield reference.group("target")


def _canonical_fragment_expectations(
    text: str,
    record: TranslationRecordLike,
    canonical_destinations: dict[tuple[str, PurePosixPath], PurePosixPath],
) -> dict[PurePosixPath, frozenset[str]]:
    fragments: dict[PurePosixPath, set[str]] = {}
    for raw in _iter_markdown_targets(text):
        _, target, _ = _split_link_target(raw)
        if not target:
            continue
        parsed = urlsplit(target)
        if (
            not parsed.fragment
            or parsed.scheme
            or parsed.netloc
            or target.startswith("/")
            or target.startswith("#")
            or not parsed.path
        ):
            continue
        try:
            source = normalize_provider_relative(
                record.canonical_source.parent,
                parsed.path,
            )
        except TranslationLinkProjectionError as exc:
            raise TranslationFragmentReconciliationError(str(exc)) from exc
        destination = _document_destination(
            record.publication,
            source,
            parsed.path,
            canonical_destinations,
        )
        if destination is not None:
            fragments.setdefault(destination, set()).add(parsed.fragment)
    return {destination: frozenset(values) for destination, values in fragments.items()}


def _rewrite_target_fragment(
    raw: str,
    record: TranslationRecordLike,
    expectations: dict[PurePosixPath, frozenset[str]],
) -> tuple[str, bool]:
    leading, target, trailing = _split_link_target(raw)
    if not target:
        return raw, False
    parsed = urlsplit(target)
    if (
        not parsed.fragment
        or parsed.scheme
        or parsed.netloc
        or target.startswith("/")
        or target.startswith("#")
        or not parsed.path
    ):
        return raw, False
    try:
        destination = normalize_provider_relative(
            record.translation_destination.parent,
            parsed.path,
        )
    except TranslationLinkProjectionError as exc:
        raise TranslationFragmentReconciliationError(str(exc)) from exc
    candidates = expectations.get(destination)
    if not candidates or parsed.fragment in candidates:
        return raw, False
    if len(candidates) != 1:
        raise TranslationFragmentReconciliationError(
            "translated fragment differs from multiple canonical candidates: "
            f"{record.translation_source} -> {target}; "
            f"canonical fragments={sorted(candidates)}"
        )
    canonical_fragment = next(iter(candidates))
    rewritten = urlunsplit(
        ("", "", parsed.path, parsed.query, canonical_fragment)
    )
    if raw.strip().startswith("<"):
        rewritten = f"<{rewritten}>"
    return f"{leading}{rewritten}{trailing}", True


def _rewrite_markdown_fragments(
    text: str,
    record: TranslationRecordLike,
    expectations: dict[PurePosixPath, frozenset[str]],
) -> tuple[str, int]:
    output: list[str] = []
    changed = 0
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            output.append(line)
            continue
        if fence_character is not None:
            output.append(line)
            continue

        def replace_inline(match: re.Match[str]) -> str:
            nonlocal changed
            if match.group("image"):
                return match.group(0)
            target, did_change = _rewrite_target_fragment(
                match.group("target"),
                record,
                expectations,
            )
            changed += int(did_change)
            return f"[{match.group('label')}]({target})"

        rewritten = INLINE_LINK.sub(replace_inline, line)
        reference = REFERENCE_TARGET.match(rewritten.rstrip("\r\n"))
        if reference:
            target, did_change = _rewrite_target_fragment(
                reference.group("target"),
                record,
                expectations,
            )
            changed += int(did_change)
            newline = rewritten[len(rewritten.rstrip("\r\n")) :]
            rewritten = (
                f"{reference.group('prefix')}{target}"
                f"{reference.group('suffix')}{newline}"
            )
        output.append(rewritten)
    return "".join(output), changed


def reconcile_translation_fragments(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
    included_pages: list[dict[str, Any]],
    records: list[TranslationRecordLike],
    docs_root: Path,
) -> int:
    """Repair only fragment drift that has unique canonical-link evidence.

    A translation may keep a historical cross-page fragment even while its
    canonical blob freshness binding is current. For each translated document,
    this function derives canonical fragment candidates from the current canonical
    source, keyed by the already-published canonical destination. A differing
    translated fragment is rewritten only when that target has exactly one
    canonical fragment candidate. Multiple candidates fail closed; targets without
    canonical fragment evidence are left untouched for downstream strict link
    validation rather than guessed.
    """
    page_destinations = {
        (page["publication"], page["document"]): page["destination"]
        for page in included_pages
    }
    canonical_destinations: dict[
        tuple[str, PurePosixPath], PurePosixPath
    ] = {}
    roots: dict[str, Path] = {}
    for publication, (root, documents, _) in publications.items():
        roots[publication] = root.resolve(strict=True)
        for document_id, document in documents.items():
            destination = page_destinations.get((publication, document_id))
            if destination is not None:
                canonical_destinations[(publication, document["source"])] = destination

    total_changed = 0
    for record in records:
        root = roots.get(record.publication)
        if root is None:
            raise TranslationFragmentReconciliationError(
                f"translation references unknown publication: {record.publication}"
            )
        canonical_file = _regular_file(
            root,
            record.canonical_source,
            f"{record.publication} canonical translation source",
        )
        translated_file = _regular_file(
            docs_root,
            record.translation_destination,
            f"{record.publication} published translation",
        )
        try:
            canonical_text = canonical_file.read_text(encoding="utf-8")
            translated_text = translated_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TranslationFragmentReconciliationError(
                f"unable to read translation fragment input: {exc}"
            ) from exc
        expectations = _canonical_fragment_expectations(
            canonical_text,
            record,
            canonical_destinations,
        )
        rewritten, changed = _rewrite_markdown_fragments(
            translated_text,
            record,
            expectations,
        )
        if changed:
            translated_file.write_text(rewritten, encoding="utf-8")
            total_changed += changed
    return total_changed
