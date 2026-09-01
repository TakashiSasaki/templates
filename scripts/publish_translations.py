#!/usr/bin/env python3
"""Validate provider translation manifests and publish non-authoritative reader pages."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from scripts.translation_link_identity import (
    TranslationLinkProjectionError,
    build_translation_projection,
    normalize_provider_relative,
    project_translation_target,
)
from scripts.translation_manifest import (
    TranslationManifestError,
    load_translation_manifest,
)

INLINE_LINK = re.compile(
    r"(?P<image>!?)\[(?P<label>[^\]\n]*)\]\((?P<target>[^)\n]+)\)"
)
REFERENCE_TARGET = re.compile(
    r"^(?P<prefix>\s{0,3}\[(?!\^)[^\]\n]+\]:\s*)"
    r"(?P<target><[^>\n]+>|\S+)(?P<suffix>.*)$"
)
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


@dataclass(frozen=True)
class AssetRoute:
    source: PurePosixPath
    destination: PurePosixPath
    directory: bool


def _walk_path(root: Path, relative: PurePosixPath, field: str) -> Path:
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
    return current


def _regular_file(root: Path, relative: PurePosixPath, field: str) -> Path:
    current = _walk_path(root, relative, field)
    if not current.is_file():
        raise TranslationPublicationError(
            f"{field} must be an existing regular file: {relative}"
        )
    return current


def _optional_regular_file(
    root: Path,
    relative: PurePosixPath,
    field: str,
) -> Path | None:
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
        if not current.exists():
            return None
    if not current.is_file():
        raise TranslationPublicationError(
            f"{field} must be a regular file when present: {relative}"
        )
    return current


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


def _asset_routes(
    publication: str,
    root: Path,
    assets: list[dict[str, Any]],
) -> list[AssetRoute]:
    routes: list[AssetRoute] = []
    for index, asset in enumerate(assets):
        source = asset["source"]
        destination = PurePosixPath(publication) / asset["destination"]
        source_path = _walk_path(root, source, f"{publication}.assets[{index}].source")
        if not source_path.exists():
            if asset["optional"]:
                continue
            raise TranslationPublicationError(
                f"required publication asset does not exist: {source}"
            )
        if not source_path.is_file() and not source_path.is_dir():
            raise TranslationPublicationError(
                f"publication asset must be a regular file or directory: {source}"
            )
        routes.append(
            AssetRoute(
                source=source,
                destination=destination,
                directory=source_path.is_dir(),
            )
        )

    if not assets:
        legacy = root / "assets"
        if legacy.is_symlink():
            raise TranslationPublicationError(
                f"{publication} legacy asset root must not be a symlink"
            )
        if legacy.is_dir():
            routes.append(
                AssetRoute(
                    source=PurePosixPath("assets"),
                    destination=PurePosixPath(publication) / "assets",
                    directory=True,
                )
            )
    return routes


def _map_asset(
    source: PurePosixPath,
    routes: list[AssetRoute],
) -> PurePosixPath | None:
    for route in sorted(routes, key=lambda item: len(item.source.parts), reverse=True):
        if route.directory:
            if source == route.source:
                return route.destination
            if route.source in source.parents:
                return route.destination / source.relative_to(route.source)
        elif source == route.source:
            return route.destination
    return None


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
    trailing_slash: bool = False,
) -> str:
    value = posixpath.relpath(
        target.as_posix(),
        start=current.parent.as_posix(),
    )
    if trailing_slash and not value.endswith("/"):
        value += "/"
    return value


def _document_source(
    publication: str,
    source: PurePosixPath,
    raw_path: str,
    canonical_destinations: dict[tuple[str, PurePosixPath], PurePosixPath],
) -> PurePosixPath | None:
    if (publication, source) in canonical_destinations:
        return source
    index_source = source / "index.md"
    if raw_path.endswith("/") or not source.suffix:
        if (publication, index_source) in canonical_destinations:
            return index_source
    return None


def _rewrite_link(
    raw: str,
    record: TranslationRecord,
    canonical_destinations: dict[tuple[str, PurePosixPath], PurePosixPath],
    translated_destinations: dict[
        tuple[str, str, PurePosixPath], PurePosixPath
    ],
    asset_routes: dict[str, list[AssetRoute]],
    translation_projections: dict[
        str, dict[PurePosixPath, PurePosixPath]
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

    try:
        translated_target = normalize_provider_relative(
            record.translation_source.parent,
            parsed.path,
        )
        target_source = project_translation_target(
            translated_target,
            parsed.path,
            translation_projections.get(record.publication, {}),
        )
    except TranslationLinkProjectionError as exc:
        raise TranslationPublicationError(str(exc)) from exc

    document_source = _document_source(
        record.publication,
        target_source,
        parsed.path,
        canonical_destinations,
    )
    destination: PurePosixPath
    trailing_slash = False
    if document_source is not None:
        translated_key = (
            record.publication,
            record.language,
            document_source,
        )
        if parsed.fragment:
            destination = canonical_destinations[
                (record.publication, document_source)
            ]
        elif translated_key in translated_destinations:
            destination = translated_destinations[translated_key]
        else:
            destination = canonical_destinations[
                (record.publication, document_source)
            ]
    else:
        asset_destination = _map_asset(
            target_source,
            asset_routes.get(record.publication, []),
        )
        if asset_destination is None:
            raise TranslationPublicationError(
                "translation link does not resolve to a published canonical "
                f"document or asset: {record.translation_source} -> {target}"
            )
        destination = asset_destination
        trailing_slash = parsed.path.endswith("/")

    rewritten_path = _relative_destination(
        record.translation_destination,
        destination,
        trailing_slash=trailing_slash,
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
    asset_routes: dict[str, list[AssetRoute]],
    translation_projections: dict[
        str, dict[PurePosixPath, PurePosixPath]
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

        def replace_inline(match: re.Match[str]) -> str:
            target = _rewrite_link(
                match.group("target"),
                record,
                canonical_destinations,
                translated_destinations,
                asset_routes,
                translation_projections,
            )
            return f"{match.group('image')}[{match.group('label')}]({target})"

        rewritten = INLINE_LINK.sub(replace_inline, line)
        reference = REFERENCE_TARGET.match(rewritten.rstrip("\r\n"))
        if reference:
            target = _rewrite_link(
                reference.group("target"),
                record,
                canonical_destinations,
                translated_destinations,
                asset_routes,
                translation_projections,
            )
            newline = rewritten[len(rewritten.rstrip("\r\n")) :]
            rewritten = (
                f"{reference.group('prefix')}{target}"
                f"{reference.group('suffix')}{newline}"
            )
        output.append(rewritten)
    return "".join(output)


def _load_records(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
    included_pages: list[dict[str, Any]],
    *,
    skip_stale: bool,
) -> tuple[
    list[TranslationRecord],
    dict[tuple[str, PurePosixPath], PurePosixPath],
    dict[str, list[AssetRoute]],
    dict[str, dict[PurePosixPath, PurePosixPath]],
]:
    page_destinations = {
        (page["publication"], page["document"]): page["destination"]
        for page in included_pages
    }
    canonical_destinations: dict[
        tuple[str, PurePosixPath], PurePosixPath
    ] = {}
    publication_asset_routes: dict[str, list[AssetRoute]] = {}
    for publication, (root, documents, assets) in publications.items():
        for document_id, document in documents.items():
            destination = page_destinations.get((publication, document_id))
            if destination is not None:
                canonical_destinations[(publication, document["source"])] = destination
        publication_asset_routes[publication] = _asset_routes(
            publication,
            root,
            assets,
        )

    records: list[TranslationRecord] = []
    translation_projections: dict[
        str, dict[PurePosixPath, PurePosixPath]
    ] = {}
    manifest_relative = PurePosixPath("translations/manifest.json")
    for publication, (root, documents, _) in sorted(publications.items()):
        label = f"{publication} translation manifest"
        manifest_path = _optional_regular_file(root, manifest_relative, label)
        if manifest_path is None:
            translation_projections[publication] = {}
            continue
        try:
            manifest = load_translation_manifest(
                manifest_path,
                label,
                publication_root=root,
            )
            translation_projections[publication] = build_translation_projection(
                manifest.entries
            )
        except (TranslationManifestError, TranslationLinkProjectionError) as exc:
            raise TranslationPublicationError(str(exc)) from exc

        source_to_document = {
            document["source"]: document_id
            for document_id, document in documents.items()
        }
        for entry in manifest.for_surface("reader"):
            field = f"{publication}.translations[{entry.index}]"
            canonical = entry.canonical
            translation = entry.translation
            language = entry.language

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

            _regular_file(root, canonical, f"{field}.canonical")
            source_file = _regular_file(root, translation, f"{field}.translation")
            if entry.current_blob_sha is None:
                raise TranslationPublicationError(
                    f"{field}.canonical freshness was not bound to provider bytes"
                )
            if not entry.is_current:
                if skip_stale:
                    continue
                raise TranslationPublicationError(
                    f"stale translation for {publication}:{canonical}: expected "
                    f"{entry.canonical_blob_sha}, current {entry.current_blob_sha}"
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

    return (
        records,
        canonical_destinations,
        publication_asset_routes,
        translation_projections,
    )


def publish_translations(
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ],
    included_pages: list[dict[str, Any]],
    docs_root: Path,
    *,
    skip_stale: bool = False,
) -> list[TranslationRecord]:
    """Publish explicitly declared reader translations.

    Direct callers remain strict by default. The integrated Site build passes
    ``skip_stale=True`` so stale non-authoritative derivatives are unavailable
    without invalidating otherwise valid canonical English pages.
    """
    (
        records,
        canonical_destinations,
        asset_routes,
        translation_projections,
    ) = _load_records(
        publications,
        included_pages,
        skip_stale=skip_stale,
    )
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
            asset_routes,
            translation_projections,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rewritten, encoding="utf-8")

    return records
