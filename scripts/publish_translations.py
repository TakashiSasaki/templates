#!/usr/bin/env python3
"""Validate provider translation manifests and publish non-authoritative reader pages."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

LANGUAGE = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
BLOB_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
JA_NOTICE = "> **参考訳（非正本）:**"


class TranslationPublicationError(RuntimeError):
    """Raised when provider translation publication state is unsafe or inconsistent."""


@dataclass(frozen=True)
class TranslationRecord:
    publication: str
    language: str
    canonical_source: PurePosixPath
    translation_source: PurePosixPath
    canonical_destination: PurePosixPath
    translation_destination: PurePosixPath
    source_file: Path


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationPublicationError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TranslationPublicationError(
                    f"{label} contains duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise TranslationPublicationError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TranslationPublicationError(f"{label} must be an object")
    return value


def _safe_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise TranslationPublicationError(
            f"{field} must be a safe relative POSIX path"
        )
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise TranslationPublicationError(
            f"{field} must be a safe relative POSIX path"
        )
    path = PurePosixPath(value)
    if path.is_absolute():
        raise TranslationPublicationError(
            f"{field} must be a safe relative POSIX path"
        )
    return path


def _regular_file(root: Path, relative: PurePosixPath, field: str) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise TranslationPublicationError(
                f"{field} must remain within publication root: {relative}"
            ) from exc
        if current.is_symlink():
            raise TranslationPublicationError(
                f"{field} must not traverse a symlink: {relative}"
            )
    if not current.is_file():
        raise TranslationPublicationError(
            f"{field} must be an existing regular file: {relative}"
        )
    return current


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


def _normalize_relative(base: PurePosixPath, raw: str) -> PurePosixPath:
    parts = list(base.parts)
    for part in PurePosixPath(raw).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise TranslationPublicationError(
                    f"translation link escapes the published documentation root: {raw}"
                )
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise TranslationPublicationError(
            f"translation link resolves to the published documentation root: {raw}"
        )
    return PurePosixPath(*parts)


def _validate_japanese_notice(text: str, field: str) -> None:
    lines = text.splitlines()
    index = 0
    if lines and lines[0] == "---":
        try:
            index = lines.index("---", 1) + 1
        except ValueError as exc:
            raise TranslationPublicationError(
                f"{field} has unterminated front matter"
            ) from exc
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith("# "):
        raise TranslationPublicationError(
            f"{field} must place a top-level title before its translation notice"
        )
    index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith(JA_NOTICE):
        raise TranslationPublicationError(
            f"{field} must place the non-authoritative Japanese notice after its title"
        )


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


def _relative_destination(
    current: PurePosixPath,
    target: PurePosixPath,
    *,
    preserve_trailing_slash: bool,
) -> str:
    value = posixpath.relpath(
        target.as_posix(),
        start=current.parent.as_posix(),
    )
    if preserve_trailing_slash and not value.endswith("/"):
        value += "/"
    return value


def _rewrite_link(
    raw: str,
    record: TranslationRecord,
    canonical_destinations: dict[tuple[str, PurePosixPath], PurePosixPath],
    translated_destinations: dict[
        tuple[str, str, PurePosixPath], PurePosixPath
    ],
) -> str:
    leading, target, trailing = _split_link_target(raw)
    if not target:
        return raw
    parsed = urlsplit(target)
    if (
        parsed.scheme
        or parsed.netloc
        or target.startswith("/")
        or target.startswith("#")
        or not parsed.path
    ):
        return raw

    target_source = _normalize_relative(record.canonical_source.parent, parsed.path)
    canonical_key = (record.publication, target_source)
    translated_key = (record.publication, record.language, target_source)
    if translated_key in translated_destinations:
        destination = translated_destinations[translated_key]
    elif canonical_key in canonical_destinations:
        destination = canonical_destinations[canonical_key]
    else:
        destination = _normalize_relative(
            record.canonical_destination.parent,
            parsed.path,
        )

    rewritten_path = _relative_destination(
        record.translation_destination,
        destination,
        preserve_trailing_slash=parsed.path.endswith("/"),
    )
    rewritten = urlunsplit(("", "", rewritten_path, parsed.query, parsed.fragment))
    if raw.strip().startswith("<"):
        rewritten = f"<{rewritten}>"
    return f"{leading}{rewritten}{trailing}"


def _rewrite_markdown(
    text: str,
    record: TranslationRecord,
    canonical_destinations: dict[tuple[str, PurePosixPath], PurePosixPath],
    translated_destinations: dict[
        tuple[str, str, PurePosixPath], PurePosixPath
    ],
) -> str:
    output: list[str] = []
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

        def replace(match: re.Match[str]) -> str:
            label = match.group(1)
            target = _rewrite_link(
                match.group(2),
                record,
                canonical_destinations,
                translated_destinations,
            )
            return f"[{label}]({target})"

        output.append(MARKDOWN_LINK.sub(replace, line))
    return "".join(output)


def _load_records(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
    included_pages: list[dict[str, Any]],
) -> tuple[
    list[TranslationRecord],
    dict[tuple[str, PurePosixPath], PurePosixPath],
]:
    page_destinations = {
        (page["publication"], page["document"]): page["destination"]
        for page in included_pages
    }
    canonical_destinations: dict[
        tuple[str, PurePosixPath], PurePosixPath
    ] = {}
    for publication, (_, documents, _) in publications.items():
        for document_id, document in documents.items():
            destination = page_destinations.get((publication, document_id))
            if destination is not None:
                canonical_destinations[(publication, document["source"])] = destination

    records: list[TranslationRecord] = []
    seen_pairs: set[tuple[str, str, PurePosixPath]] = set()
    seen_translation_paths: set[tuple[str, PurePosixPath]] = set()

    for publication, (root, documents, _) in sorted(publications.items()):
        manifest_path = root / "translations" / "manifest.json"
        if not manifest_path.exists():
            continue
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise TranslationPublicationError(
                f"{publication} translation manifest must be a regular file"
            )
        manifest = _read_json(manifest_path, f"{publication} translation manifest")
        if set(manifest) != {"schema_version", "canonical_language", "translations"}:
            raise TranslationPublicationError(
                f"{publication} translation manifest has unsupported fields"
            )
        if manifest["schema_version"] != 1 or isinstance(
            manifest["schema_version"], bool
        ):
            raise TranslationPublicationError(
                f"{publication} translation manifest schema_version must be integer 1"
            )
        if manifest["canonical_language"] != "en":
            raise TranslationPublicationError(
                f"{publication} translation manifest canonical_language must be en"
            )
        entries = manifest["translations"]
        if not isinstance(entries, list):
            raise TranslationPublicationError(
                f"{publication} translation manifest translations must be an array"
            )

        source_to_document = {
            document["source"]: document_id
            for document_id, document in documents.items()
        }
        for index, entry in enumerate(entries):
            field = f"{publication}.translations[{index}]"
            required = {
                "canonical",
                "language",
                "translation",
                "canonical_blob_sha",
            }
            if not isinstance(entry, dict) or set(entry) != required:
                raise TranslationPublicationError(
                    f"{field} must contain canonical, language, translation, "
                    "and canonical_blob_sha"
                )
            canonical = _safe_path(entry["canonical"], f"{field}.canonical")
            translation = _safe_path(entry["translation"], f"{field}.translation")
            language = entry["language"]
            blob_sha = entry["canonical_blob_sha"]
            if (
                not isinstance(language, str)
                or not LANGUAGE.fullmatch(language)
                or language == "en"
            ):
                raise TranslationPublicationError(
                    f"{field}.language must be a non-English lowercase language tag"
                )
            if not isinstance(blob_sha, str) or not BLOB_SHA.fullmatch(blob_sha):
                raise TranslationPublicationError(
                    f"{field}.canonical_blob_sha must be a full lowercase Git blob SHA"
                )
            if canonical.suffix.lower() != ".md" or translation.suffix.lower() != ".md":
                raise TranslationPublicationError(
                    f"{field} canonical and translation paths must be Markdown"
                )
            document_id = source_to_document.get(canonical)
            if document_id is None:
                raise TranslationPublicationError(
                    f"{field}.canonical is not in the canonical publication catalog"
                )
            canonical_destination = page_destinations.get((publication, document_id))
            if canonical_destination is None:
                raise TranslationPublicationError(
                    f"{field}.canonical is not included in the assembled site"
                )
            expected_translation = PurePosixPath("translations") / language / canonical
            if translation != expected_translation:
                raise TranslationPublicationError(
                    f"{field}.translation must mirror canonical at {expected_translation}"
                )

            pair = (publication, language, canonical)
            translation_key = (publication, translation)
            if pair in seen_pairs:
                raise TranslationPublicationError(
                    f"duplicate translation pair: {publication} {language} {canonical}"
                )
            if translation_key in seen_translation_paths:
                raise TranslationPublicationError(
                    f"duplicate translation path: {publication} {translation}"
                )
            seen_pairs.add(pair)
            seen_translation_paths.add(translation_key)

            canonical_file = _regular_file(root, canonical, f"{field}.canonical")
            source_file = _regular_file(root, translation, f"{field}.translation")
            actual_sha = _git_blob_sha(canonical_file)
            if actual_sha != blob_sha:
                raise TranslationPublicationError(
                    f"stale translation for {publication}:{canonical}: expected "
                    f"{blob_sha}, current {actual_sha}"
                )
            try:
                text = source_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise TranslationPublicationError(
                    f"unable to read translation source {source_file}: {exc}"
                ) from exc
            if language == "ja":
                _validate_japanese_notice(text, field)

            records.append(
                TranslationRecord(
                    publication=publication,
                    language=language,
                    canonical_source=canonical,
                    translation_source=translation,
                    canonical_destination=canonical_destination,
                    translation_destination=PurePosixPath(language)
                    / canonical_destination,
                    source_file=source_file,
                )
            )

    return records, canonical_destinations


def publish_translations(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
    included_pages: list[dict[str, Any]],
    docs_root: Path,
) -> list[TranslationRecord]:
    """Publish only explicitly declared, synchronized provider translations."""
    records, canonical_destinations = _load_records(publications, included_pages)
    translated_destinations = {
        (record.publication, record.language, record.canonical_source):
        record.translation_destination
        for record in records
    }
    if len(translated_destinations) != len(records):
        raise TranslationPublicationError("translation destination mapping is not unique")

    output_destinations: set[PurePosixPath] = set()
    for record in records:
        if record.translation_destination in output_destinations:
            raise TranslationPublicationError(
                f"duplicate translated output: {record.translation_destination}"
            )
        output_destinations.add(record.translation_destination)
        target = docs_root.joinpath(*record.translation_destination.parts)
        try:
            target.relative_to(docs_root)
        except ValueError as exc:
            raise TranslationPublicationError(
                f"translation output escapes documentation root: "
                f"{record.translation_destination}"
            ) from exc
        if target.exists() or target.is_symlink():
            raise TranslationPublicationError(f"translation output collision: {target}")
        try:
            text = record.source_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TranslationPublicationError(
                f"unable to read translation source {record.source_file}: {exc}"
            ) from exc
        rewritten = _rewrite_markdown(
            text,
            record,
            canonical_destinations,
            translated_destinations,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rewritten, encoding="utf-8")

    return records
