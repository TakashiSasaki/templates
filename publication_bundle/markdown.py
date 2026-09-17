"""Markdown link projection from resolved publication records."""
from __future__ import annotations
import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, unquote

SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


FENCE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})(?:[^`~].*)?$")


REFERENCE = re.compile(
    r"^(?P<prefix>[ \t]{0,3}\[[^\]\n]+\]:[ \t]*)(?P<destination><[^>\n]+>|\S+)"
)


AssetRule = tuple[PurePosixPath, PurePosixPath, bool]


def _normalise_source_path(
    base: PurePosixPath,
    raw_path: str,
) -> PurePosixPath | None:
    if not raw_path or raw_path.startswith("/") or "\\" in raw_path:
        return None

    parts: list[str] = []
    for part in (base / PurePosixPath(unquote(raw_path))).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)

    if not parts:
        return PurePosixPath(".")
    return PurePosixPath(*parts)


def _split_destination(
    destination: str,
) -> tuple[bool, str, str] | None:
    angle_wrapped = destination.startswith("<") and destination.endswith(">")
    value = destination[1:-1] if angle_wrapped else destination

    if (
        not value
        or value.startswith("#")
        or value.startswith("/")
        or value.startswith("//")
        or SCHEME.match(value)
    ):
        return None

    path_and_query, hash_separator, fragment = value.partition("#")
    path, query_separator, query = path_and_query.partition("?")
    if not path:
        return None

    suffix = ""
    if query_separator:
        suffix += query_separator + query
    if hash_separator:
        suffix += hash_separator + fragment
    return angle_wrapped, path, suffix


def _asset_target(
    source_path: PurePosixPath,
    rules: list[AssetRule],
    docs_root: Path,
) -> PurePosixPath | None:
    for source, destination, is_directory in rules:
        if is_directory:
            try:
                relative = source_path.relative_to(source)
            except ValueError:
                continue
            target = destination / relative
        elif source_path == source:
            target = destination
        else:
            continue

        if docs_root.joinpath(*target.parts).exists():
            return target
    return None


def _rewrite_destination(
    destination: str,
    *,
    source_document: PurePosixPath,
    site_document: PurePosixPath,
    document_targets: dict[PurePosixPath, PurePosixPath],
    asset_rules: list[AssetRule],
    docs_root: Path,
    publication: str,
    site_source_paths: frozenset[bytes] | None,
    site_source_url: Any | None,
) -> str:
    parsed = _split_destination(destination)
    if parsed is None:
        return destination
    angle_wrapped, raw_path, suffix = parsed

    source_target = _normalise_source_path(source_document.parent, raw_path)
    if source_target is None:
        return destination

    site_target = document_targets.get(source_target)
    if site_target is None and raw_path.endswith("/"):
        site_target = document_targets.get(source_target / "index.md")
    if site_target is None:
        site_target = _asset_target(source_target, asset_rules, docs_root)
    if site_target is None:
        if publication == "site" and site_source_paths is not None:
            encoded_path = source_target.as_posix().encode("utf-8")
            if encoded_path in site_source_paths:
                if site_source_url is None:
                    raise ValueError("Site source URL helper is required")
                return site_source_url(source_target.as_posix(), suffix)
        return destination

    start = site_document.parent.as_posix()
    if start == ".":
        start = "."
    relative = posixpath.relpath(site_target.as_posix(), start=start)
    relative = quote(relative, safe="/@-._~") + suffix
    if angle_wrapped:
        return f"<{relative}>"
    return relative


def _inline_code_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(line):
        start = line.find("`", cursor)
        if start < 0:
            break
        width = 1
        while start + width < len(line) and line[start + width] == "`":
            width += 1
        marker = "`" * width
        end = line.find(marker, start + width)
        if end < 0:
            cursor = start + width
            continue
        spans.append((start, end + width))
        cursor = end + width
    return spans


def _in_spans(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _rewrite_inline_links(
    line: str,
    rewrite: Any,
) -> tuple[str, int]:
    spans = _inline_code_spans(line)
    replacements: list[tuple[int, int, str]] = []
    cursor = 0

    while True:
        marker = line.find("](", cursor)
        if marker < 0:
            break
        if _in_spans(marker, spans):
            cursor = marker + 2
            continue

        start = marker + 2
        while start < len(line) and line[start] in " \t":
            start += 1
        if start >= len(line):
            break

        if line[start] == "<":
            end = line.find(">", start + 1)
            if end < 0:
                cursor = start + 1
                continue
            end += 1
        else:
            end = start
            nested_parentheses = 0
            while end < len(line):
                character = line[end]
                if character == "\\" and end + 1 < len(line):
                    end += 2
                    continue
                if character == "(":
                    nested_parentheses += 1
                elif character == ")":
                    if nested_parentheses == 0:
                        break
                    nested_parentheses -= 1
                elif character in " \t\r\n" and nested_parentheses == 0:
                    break
                end += 1

        if end <= start:
            cursor = start + 1
            continue

        original = line[start:end]
        updated = rewrite(original)
        if updated != original:
            replacements.append((start, end, updated))
        cursor = end

    if not replacements:
        return line, 0

    result = line
    for start, end, value in reversed(replacements):
        result = result[:start] + value + result[end:]
    return result, len(replacements)


def _rewrite_reference_definition(
    line: str,
    rewrite: Any,
) -> tuple[str, int]:
    match = REFERENCE.match(line)
    if match is None or _in_spans(match.start("destination"), _inline_code_spans(line)):
        return line, 0
    original = match.group("destination")
    updated = rewrite(original)
    if updated == original:
        return line, 0
    start, end = match.span("destination")
    return line[:start] + updated + line[end:], 1


def _rewrite_markdown(
    text: str,
    *,
    source_document: PurePosixPath,
    site_document: PurePosixPath,
    document_targets: dict[PurePosixPath, PurePosixPath],
    asset_rules: list[AssetRule],
    docs_root: Path,
    publication: str,
    site_source_paths: frozenset[bytes] | None,
    site_source_url: Any | None = None,
) -> tuple[str, int]:
    def rewrite(destination: str) -> str:
        return _rewrite_destination(
            destination,
            source_document=source_document,
            site_document=site_document,
            document_targets=document_targets,
            asset_rules=asset_rules,
            docs_root=docs_root,
            publication=publication,
            site_source_paths=site_source_paths,
            site_source_url=site_source_url,
        )

    output: list[str] = []
    rewrites = 0
    open_fence: tuple[str, int] | None = None

    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        fence_match = FENCE.match(stripped)
        if open_fence is not None:
            if fence_match is not None:
                marker = fence_match.group("fence")
                if marker[0] == open_fence[0] and len(marker) >= open_fence[1]:
                    open_fence = None
            output.append(line)
            continue
        if fence_match is not None:
            marker = fence_match.group("fence")
            open_fence = (marker[0], len(marker))
            output.append(line)
            continue

        line, count = _rewrite_reference_definition(line, rewrite)
        rewrites += count
        line, count = _rewrite_inline_links(line, rewrite)
        rewrites += count
        output.append(line)

    return "".join(output), rewrites
