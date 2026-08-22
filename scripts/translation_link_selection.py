#!/usr/bin/env python3
"""Select localized reader routes only when a current translation exists."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Iterable, Protocol
from urllib.parse import urlsplit, urlunsplit

INLINE_LINK = re.compile(
    r"(?P<image>!?)\[(?P<label>[^\]\n]*)\]\((?P<target>[^)\n]+)\)"
)
REFERENCE_TARGET = re.compile(
    r"^(?P<prefix>\s{0,3}\[(?!\^)[^\]\n]+\]:\s*)"
    r"(?P<target><[^>\n]+>|\S+)(?P<suffix>.*)$"
)
HTML_HREF = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


class TranslationLinkSelectionError(RuntimeError):
    """Raised when localized reader-link selection state is inconsistent."""


class TranslationRouteRecord(Protocol):
    language: str
    canonical_destination: PurePosixPath
    translation_destination: PurePosixPath


def reader_route(destination: PurePosixPath) -> str:
    """Convert an assembled Markdown destination to its directory-style reader URL."""
    if destination.suffix != ".md":
        raise TranslationLinkSelectionError(
            f"reader destination must be Markdown: {destination}"
        )
    parts = list(destination.parts)
    filename = parts.pop()
    if filename != "index.md":
        parts.append(filename[:-3])
    if not parts:
        return "/"
    return "/" + "/".join(parts) + "/"


def _route_aliases(route: str) -> tuple[str, ...]:
    if route == "/":
        return (route,)
    return (route, route[:-1])


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


def _current_route_map(
    records: Iterable[TranslationRouteRecord],
) -> dict[tuple[str, str], str]:
    routes: dict[tuple[str, str], str] = {}
    for record in records:
        canonical = reader_route(record.canonical_destination)
        localized = reader_route(record.translation_destination)
        for alias in _route_aliases(canonical):
            key = (record.language, alias)
            previous = routes.get(key)
            if previous is not None and previous != localized:
                raise TranslationLinkSelectionError(
                    f"conflicting localized route for {record.language}:{alias}: "
                    f"{previous} vs {localized}"
                )
            routes[key] = localized
    return routes


def _rewrite_target(
    raw: str,
    language: str,
    routes: dict[tuple[str, str], str],
) -> tuple[str, bool]:
    leading, target, trailing = _split_link_target(raw)
    if not target:
        return raw, False
    parsed = urlsplit(target)
    if (
        parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
    ):
        return raw, False
    localized = routes.get((language, parsed.path))
    if localized is None:
        return raw, False
    rewritten = urlunsplit(("", "", localized, parsed.query, parsed.fragment))
    if raw.strip().startswith("<"):
        rewritten = f"<{rewritten}>"
    return f"{leading}{rewritten}{trailing}", True


def _rewrite_markdown(
    text: str,
    language: str,
    routes: dict[tuple[str, str], str],
) -> tuple[str, int]:
    output: list[str] = []
    rewrite_count = 0
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
            nonlocal rewrite_count
            if match.group("image"):
                return match.group(0)
            target, changed = _rewrite_target(
                match.group("target"),
                language,
                routes,
            )
            if changed:
                rewrite_count += 1
            return f"[{match.group('label')}]({target})"

        rewritten = INLINE_LINK.sub(replace_inline, line)
        reference = REFERENCE_TARGET.match(rewritten.rstrip("\r\n"))
        if reference:
            target, changed = _rewrite_target(
                reference.group("target"),
                language,
                routes,
            )
            if changed:
                rewrite_count += 1
            newline = rewritten[len(rewritten.rstrip("\r\n")) :]
            rewritten = (
                f"{reference.group('prefix')}{target}"
                f"{reference.group('suffix')}{newline}"
            )

        def replace_href(match: re.Match[str]) -> str:
            nonlocal rewrite_count
            target, changed = _rewrite_target(
                match.group("target"),
                language,
                routes,
            )
            if changed:
                rewrite_count += 1
            return (
                f"{match.group('prefix')}{match.group('quote')}"
                f"{target}{match.group('quote')}"
            )

        rewritten = HTML_HREF.sub(replace_href, rewritten)
        output.append(rewritten)

    return "".join(output), rewrite_count


def rewrite_current_localized_links(
    records: Iterable[TranslationRouteRecord],
    docs_root: Path,
) -> int:
    """Rewrite root-relative reader links to available localized destinations.

    ``records`` must contain only translations that are current and actually
    published. A canonical route therefore remains untouched when its localized
    derivative is missing or stale.
    """
    current = list(records)
    routes = _current_route_map(current)
    root = docs_root.resolve(strict=True)
    rewrite_count = 0

    for record in current:
        path = docs_root.joinpath(*record.translation_destination.parts)
        try:
            path.relative_to(docs_root)
        except ValueError as exc:
            raise TranslationLinkSelectionError(
                f"translation destination escapes documentation root: "
                f"{record.translation_destination}"
            ) from exc
        if path.is_symlink() or not path.is_file():
            raise TranslationLinkSelectionError(
                f"published translation must be a regular file: "
                f"{record.translation_destination}"
            )
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise TranslationLinkSelectionError(
                f"published translation escapes documentation root: "
                f"{record.translation_destination}"
            ) from exc
        text = path.read_text(encoding="utf-8")
        rewritten, changed = _rewrite_markdown(text, record.language, routes)
        if changed:
            path.write_text(rewritten, encoding="utf-8")
            rewrite_count += changed

    return rewrite_count
