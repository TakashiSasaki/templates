#!/usr/bin/env python3
"""Generate a deterministic navigation graph from provider-owned index.md files."""

from __future__ import annotations

import argparse
import html
import html.entities
import ipaddress
import json
import os
import posixpath
import re
import string
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import SplitResult, unquote_to_bytes, urlsplit, urlunsplit

try:
    from scripts.generate_repository_file_previews import BIDIRECTIONAL_CONTROLS
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        parse_ls_tree,
    )
except ModuleNotFoundError:
    from generate_repository_file_previews import BIDIRECTIONAL_CONTROLS
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        parse_ls_tree,
    )


PROVIDER_ORDER = ("skill", "policy", "webapp")
ROOT_INDEX = "docs/index.md"
MAX_INDEX_BYTES = 256 * 1024
REGULAR_FILE_MODES = frozenset({"100644", "100755"})
MARKDOWN_ESCAPABLE = frozenset(string.punctuation)
NON_MARKDOWN_LINE_SEPARATORS = frozenset({"\u2028", "\u2029"})
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
CLOSING_ATX = re.compile(r"[ \t]+#+[ \t]*$")
FORBIDDEN_DOMAIN_CHARACTERS = frozenset("#/:<>?@[\\]^|%")
IPV4_NUMBER = re.compile(r"\A(?:0[xX][0-9A-Fa-f]*|0[0-7]*|[0-9]+)\Z")
COMMONMARK_CHARACTER_REFERENCE = re.compile(
    r"&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});"
)
LINK_ENTRY = re.compile(
    r"^[*-][ \t]+\[((?:\\.|[^\]])+)\]\((.+?)\)[ \t]+[-–—][ \t]+(.+?)[ \t]*$"
)


class IndexNavigationError(RuntimeError):
    """Raised when an index navigation graph cannot be produced safely."""


@dataclass(frozen=True)
class ParsedLink:
    label: str
    raw_target: str
    description: str
    section: str | None
    line: int


@dataclass(frozen=True)
class ParsedSection:
    title: str
    level: int


@dataclass(frozen=True)
class ParsedIndex:
    title: str
    sections: tuple[ParsedSection, ...]
    links: tuple[ParsedLink, ...]


def contains_disallowed_control(
    value: str,
    *,
    allow_layout_whitespace: bool = True,
) -> bool:
    for character in value:
        codepoint = ord(character)
        if (
            (codepoint < 32 and (not allow_layout_whitespace or character not in "\t\n\r"))
            or 0x7F <= codepoint <= 0x9F
            or character in BIDIRECTIONAL_CONTROLS
        ):
            return True
    return False


def decode_index_text(content: bytes, path: str) -> str:
    if len(content) > MAX_INDEX_BYTES:
        raise IndexNavigationError(
            f"index exceeds {MAX_INDEX_BYTES // 1024} KiB limit: {path}"
        )
    if b"\0" in content:
        raise IndexNavigationError(f"index contains a NUL byte: {path}")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(f"index is not strict UTF-8: {path}") from exc
    if contains_disallowed_control(text):
        raise IndexNavigationError(
            f"index contains a disallowed control character: {path}"
        )
    if any(separator in text for separator in NON_MARKDOWN_LINE_SEPARATORS):
        raise IndexNavigationError(
            f"index contains a non-Markdown line separator: {path}"
        )
    return text


def normalize_heading_value(value: str) -> str:
    """Remove Markdown's optional closing ATX marker from a heading value."""
    trimmed = value.strip(" \t")
    if trimmed and all(character == "#" for character in trimmed):
        return ""
    return CLOSING_ATX.sub("", value).strip(" \t")


def list_marker_indent_columns(line: str) -> int:
    """Return CommonMark indentation columns between a bullet marker and link text."""
    bracket = line.find("[", 1)
    if bracket < 0:
        return 0
    column = 1
    start_column = column
    for character in line[1:bracket]:
        if character == " ":
            column += 1
        elif character == "\t":
            column += 4 - (column % 4)
        else:
            return 0
    return column - start_column


def parse_index(text: str, path: str) -> ParsedIndex:
    title: str | None = None
    section: str | None = None
    sections: list[ParsedSection] = []
    section_names: set[str] = set()
    links: list[ParsedLink] = []
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")

    for line_number, raw_line in enumerate(normalized_text.split("\n"), start=1):
        if not raw_line.strip(" \t"):
            continue
        leading = raw_line[: len(raw_line) - len(raw_line.lstrip(" \t"))]
        if "\t" in leading or len(leading) >= 4:
            raise IndexNavigationError(
                f"indented code-block content is not allowed in {path}:{line_number}"
            )

        line = raw_line.strip(" \t")
        heading = HEADING.fullmatch(line)
        if heading:
            level = len(heading.group(1))
            value = normalize_heading_value(heading.group(2))
            if not value:
                raise IndexNavigationError(f"empty heading in {path}:{line_number}")
            if level == 1:
                if title is not None:
                    raise IndexNavigationError(
                        f"multiple level-1 headings in {path}:{line_number}"
                    )
                title = value
                section = None
            else:
                if title is None:
                    raise IndexNavigationError(
                        f"section precedes title in {path}:{line_number}"
                    )
                if value in section_names:
                    raise IndexNavigationError(
                        f"duplicate section heading in {path}:{line_number}: {value!r}"
                    )
                section_names.add(value)
                section = value
                sections.append(ParsedSection(title=value, level=level))
            continue

        entry = LINK_ENTRY.fullmatch(line)
        if entry:
            marker_indent = list_marker_indent_columns(line)
            if not 1 <= marker_indent <= 4:
                raise IndexNavigationError(
                    f"list marker indentation must be 1 to 4 columns in "
                    f"{path}:{line_number}"
                )
            label_source = entry.group(1)
            trailing_backslashes = len(label_source) - len(label_source.rstrip("\\"))
            if trailing_backslashes % 2:
                raise IndexNavigationError(
                    f"escaped link-label terminator in {path}:{line_number}"
                )
            if title is None:
                raise IndexNavigationError(
                    f"link precedes title in {path}:{line_number}"
                )
            label = decode_commonmark_inline_text(label_source.strip(" \t")).strip(" \t")
            if contains_disallowed_control(label, allow_layout_whitespace=False):
                raise IndexNavigationError(
                    f"link label contains a disallowed control character in "
                    f"{path}:{line_number}"
                )
            raw_target = entry.group(2).strip(" \t")
            destination_backslashes = len(raw_target) - len(raw_target.rstrip("\\"))
            if destination_backslashes % 2:
                raise IndexNavigationError(
                    f"escaped link-destination terminator in {path}:{line_number}"
                )
            description = entry.group(3).strip(" \t")
            if not label:
                raise IndexNavigationError(
                    f"link label is empty in {path}:{line_number}"
                )
            links.append(
                ParsedLink(
                    label=label,
                    raw_target=raw_target,
                    description=description,
                    section=section,
                    line=line_number,
                )
            )
            continue

        raise IndexNavigationError(
            f"unsupported index.md content in {path}:{line_number}: {raw_line!r}"
        )

    if title is None:
        raise IndexNavigationError(f"index is missing a level-1 heading: {path}")
    return ParsedIndex(
        title=title,
        sections=tuple(sections),
        links=tuple(links),
    )


def decode_fragment(value: str, source: str, line: int) -> str | None:
    if not value:
        return None
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(
            f"link fragment is not UTF-8 in {source}:{line}: {value!r}"
        ) from exc
    if "\x00" in decoded:
        raise IndexNavigationError(
            f"link fragment contains a NUL byte in {source}:{line}: {value!r}"
        )
    if contains_disallowed_control(decoded, allow_layout_whitespace=False):
        raise IndexNavigationError(
            f"link fragment contains a disallowed control character in "
            f"{source}:{line}: {value!r}"
        )
    return decoded


def decode_link_path(value: str, source: str, line: int) -> tuple[str, bool]:
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(
            f"link path is not UTF-8 in {source}:{line}: {value!r}"
        ) from exc
    if not decoded or decoded.startswith("/") or "\x00" in decoded:
        raise IndexNavigationError(
            f"unsafe repository-relative link in {source}:{line}: {value!r}"
        )
    if contains_disallowed_control(decoded, allow_layout_whitespace=False):
        raise IndexNavigationError(
            f"link path contains a disallowed control character in "
            f"{source}:{line}: {value!r}"
        )

    final_component = decoded.rsplit("/", maxsplit=1)[-1]
    directory_marker = decoded.endswith("/") or final_component in {".", ".."}
    normalized = posixpath.normpath(posixpath.join(posixpath.dirname(source), decoded))
    if normalized == ".." or normalized.startswith("../"):
        raise IndexNavigationError(
            f"link escapes repository root in {source}:{line}: {value!r}"
        )
    return normalized, directory_marker


def validate_bare_destination_parentheses(value: str, source: str, line: int) -> None:
    """Require literal bare-destination parentheses to be balanced."""
    depth = 0
    index = 0
    while index < len(value):
        character = value[index]
        if (
            character == "\\"
            and index + 1 < len(value)
            and value[index + 1] in MARKDOWN_ESCAPABLE
        ):
            index += 2
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                raise IndexNavigationError(
                    f"unbalanced link destination parentheses in "
                    f"{source}:{line}: {value!r}"
                )
            depth -= 1
        index += 1
    if depth:
        raise IndexNavigationError(
            f"unbalanced link destination parentheses in {source}:{line}: {value!r}"
        )


def unwrap_pointy_destination(value: str, source: str, line: int) -> tuple[str, bool]:
    """Return CommonMark pointy destination content and whether pointy syntax was used."""
    if not value.startswith("<"):
        return value, False
    if len(value) < 2 or not value.endswith(">"):
        raise IndexNavigationError(
            f"malformed pointy link destination in {source}:{line}: {value!r}"
        )

    inner = value[1:-1]
    trailing_backslashes = len(inner) - len(inner.rstrip("\\"))
    if trailing_backslashes % 2:
        raise IndexNavigationError(
            f"malformed pointy link destination in {source}:{line}: {value!r}"
        )

    index = 0
    while index < len(inner):
        character = inner[index]
        if (
            character == "\\"
            and index + 1 < len(inner)
            and inner[index + 1] in MARKDOWN_ESCAPABLE
        ):
            index += 2
            continue
        if character in "<>":
            raise IndexNavigationError(
                f"malformed pointy link destination in {source}:{line}: {value!r}"
            )
        index += 1
    return inner, True


def decode_commonmark_character_reference(reference: str) -> str | None:
    """Decode an exact CommonMark character reference token, if valid."""
    if reference.startswith("&#"):
        return html.unescape(reference)
    name = reference[1:]
    if name not in html.entities.html5:
        return None
    return html.entities.html5[name]


def decode_commonmark_character_references(value: str) -> str:
    """Decode only exact semicolon-terminated references accepted by CommonMark."""
    def replace(match: re.Match[str]) -> str:
        decoded = decode_commonmark_character_reference(match.group(0))
        return match.group(0) if decoded is None else decoded

    return COMMONMARK_CHARACTER_REFERENCE.sub(replace, value)


def decode_commonmark_inline_text(value: str) -> str:
    """Decode CommonMark backslash escapes and exact character references once."""
    decoded_parts: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if (
            character == "\\"
            and index + 1 < len(value)
            and value[index + 1] in MARKDOWN_ESCAPABLE
        ):
            decoded_parts.append(value[index + 1])
            index += 2
            continue
        if character == "&":
            reference = COMMONMARK_CHARACTER_REFERENCE.match(value, index)
            if reference is not None:
                decoded_reference = decode_commonmark_character_reference(reference.group(0))
                if decoded_reference is not None:
                    decoded_parts.append(decoded_reference)
                    index = reference.end()
                    continue
        decoded_parts.append(character)
        index += 1
    return "".join(decoded_parts)


def decode_markdown_destination(value: str, source: str, line: int) -> str:
    """Apply CommonMark destination delimiters, escapes, and references before URI parsing."""
    destination, pointy = unwrap_pointy_destination(value, source, line)
    if not pointy:
        if any(character == " " or ord(character) < 32 for character in destination):
            raise IndexNavigationError(
                f"link target contains invalid whitespace or controls in "
                f"{source}:{line}: {value!r}"
            )
        validate_bare_destination_parentheses(destination, source, line)

    decoded = decode_commonmark_inline_text(destination)
    if contains_disallowed_control(decoded, allow_layout_whitespace=False):
        raise IndexNavigationError(
            f"link target contains invalid whitespace or controls in "
            f"{source}:{line}: {value!r}"
        )
    return decoded


def parse_ipv4_number(value: str) -> int:
    if value.lower().startswith("0x"):
        return int(value[2:] or "0", 16)
    if len(value) > 1 and value.startswith("0"):
        return int(value[1:] or "0", 8)
    return int(value, 10)


def ipv4_ends_in_number(hostname: str) -> bool:
    """Apply the WHATWG ends-in-a-number check to an ASCII host."""
    candidate = hostname.rstrip(".")
    if not candidate:
        return False
    last = candidate.rsplit(".", maxsplit=1)[-1]
    if last.isascii() and last.isdigit():
        return True
    return re.fullmatch(r"0[xX][0-9A-Fa-f]*", last) is not None


def validate_browser_ipv4_candidate(
    hostname: str,
    source: str,
    line: int,
    target: str,
) -> bool:
    """Validate WHATWG-style IPv4 candidates; return False for ordinary domains."""
    candidate = hostname.rstrip(".")
    if not candidate or not ipv4_ends_in_number(candidate):
        return False
    parts = candidate.split(".")
    if not all(IPV4_NUMBER.fullmatch(part) for part in parts):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    try:
        numbers = [parse_ipv4_number(part) for part in parts]
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if (
        len(numbers) > 4
        or any(number > 255 for number in numbers[:-1])
        or numbers[-1] >= 256 ** (5 - len(numbers))
    ):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    return True


def contains_forbidden_domain_codepoint(value: str) -> bool:
    """Return whether an ASCII domain contains a WHATWG-forbidden domain code point."""
    return any(
        ord(character) <= 0x20
        or ord(character) == 0x7F
        or character in FORBIDDEN_DOMAIN_CHARACTERS
        for character in value
    )


def decode_external_hostname(
    hostname: str,
    source: str,
    line: int,
    target: str,
) -> str:
    """Percent-decode a special-scheme host before browser-style validation."""
    index = 0
    while index < len(hostname):
        if hostname[index] != "%":
            index += 1
            continue
        if (
            index + 2 >= len(hostname)
            or hostname[index + 1] not in string.hexdigits
            or hostname[index + 2] not in string.hexdigits
        ):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        index += 3
    try:
        decoded = unquote_to_bytes(hostname).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if (
        not decoded
        or any(character.isspace() for character in decoded)
        or contains_disallowed_control(decoded, allow_layout_whitespace=False)
    ):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    return decoded


def validate_external_location(
    parsed: SplitResult,
    source: str,
    line: int,
    target: str,
) -> None:
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if not hostname:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    hostname = decode_external_hostname(hostname, source, line, target)

    try:
        ipaddress.ip_address(hostname)
        return
    except ValueError:
        pass
    if validate_browser_ipv4_candidate(hostname, source, line, target):
        return

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii").rstrip(".")
    except UnicodeError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if validate_browser_ipv4_candidate(ascii_hostname, source, line, target):
        return
    if not ascii_hostname or contains_forbidden_domain_codepoint(ascii_hostname):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )


def resolve_link(
    source: str,
    link: ParsedLink,
    entries: dict[str, tuple[str, str, str]],
) -> dict[str, object]:
    raw_target = link.raw_target
    if contains_disallowed_control(raw_target, allow_layout_whitespace=False):
        raise IndexNavigationError(
            f"link target contains invalid whitespace or controls in "
            f"{source}:{link.line}: {raw_target!r}"
        )
    target = decode_markdown_destination(raw_target, source, link.line)
    fragment_delimiter_present = "#" in target
    query_delimiter_present = "?" in target.split("#", maxsplit=1)[0]
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed link target in {source}:{link.line}: {raw_target!r}"
        ) from exc
    fragment = decode_fragment(parsed.fragment, source, link.line)
    resolved_fragment = "" if fragment is None and fragment_delimiter_present else fragment

    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise IndexNavigationError(
                f"unsupported external link in {source}:{link.line}: {raw_target!r}"
            )
        validate_external_location(parsed, source, link.line, target)
        if query_delimiter_present:
            raise IndexNavigationError(
                f"external link must not contain a query in "
                f"{source}:{link.line}: {raw_target!r}"
            )
        external_target = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        return {
            "kind": "external",
            "target": external_target,
            "fragment": resolved_fragment,
        }

    if query_delimiter_present:
        raise IndexNavigationError(
            f"repository link must not contain a query in "
            f"{source}:{link.line}: {raw_target!r}"
        )
    if not parsed.path:
        if fragment is None and not fragment_delimiter_present:
            raise IndexNavigationError(
                f"empty link target in {source}:{link.line}"
            )
        return {
            "kind": "fragment",
            "target": source,
            "fragment": resolved_fragment,
        }

    normalized, directory_marker = decode_link_path(parsed.path, source, link.line)
    target_entry = entries.get(normalized)

    if directory_marker and target_entry is not None and target_entry[0] == "blob":
        raise IndexNavigationError(
            f"slash-terminated repository link targets a regular file in "
            f"{source}:{link.line}: {raw_target!r}"
        )

    if target_entry is None and directory_marker:
        candidate = (
            "index.md"
            if normalized == "."
            else normalized.rstrip("/") + "/index.md"
        )
        if candidate in entries:
            normalized = candidate
            target_entry = entries[candidate]
        elif normalized == ".":
            target_entry = ("tree", "040000", "")
    elif target_entry is not None and target_entry[0] == "tree":
        candidate = normalized.rstrip("/") + "/index.md"
        if candidate in entries:
            normalized = candidate
            target_entry = entries[candidate]

    if target_entry is None:
        raise IndexNavigationError(
            f"broken repository link in {source}:{link.line}: {raw_target!r} -> {normalized}"
        )

    kind, mode, _object_id = target_entry
    if kind == "tree":
        resolved_kind = "directory"
    elif kind == "blob" and mode in REGULAR_FILE_MODES:
        resolved_kind = (
            "index"
            if normalized == "index.md" or normalized.endswith("/index.md")
            else "file"
        )
    else:
        raise IndexNavigationError(
            f"link target is not a regular file or directory in "
            f"{source}:{link.line}: {normalized}"
        )
    return {
        "kind": resolved_kind,
        "target": normalized,
        "fragment": resolved_fragment,
    }


def immutable_git(root: Path, *args: str) -> bytes:
    """Inspect exact Git objects with replacement refs disabled."""
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise IndexNavigationError(
            f"unable to inspect immutable Git objects in {root}{suffix}"
        ) from exc
    return process.stdout


def immutable_object_size(root: Path, object_id: str) -> int:
    raw = immutable_git(root, "cat-file", "-s", object_id)
    try:
        size = int(raw.decode("ascii", errors="strict").strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise IndexNavigationError(
            f"git cat-file returned an invalid size for immutable blob {object_id}"
        ) from exc
    if size < 0:
        raise IndexNavigationError(f"immutable blob has an invalid size: {object_id}")
    return size


def immutable_object_content(root: Path, object_id: str) -> bytes:
    return immutable_git(root, "cat-file", "blob", object_id)


def load_reachable_index(
    root: Path,
    path: str,
    entry: tuple[str, str, str] | None,
) -> tuple[str, ParsedIndex]:
    if entry is None or entry[0] != "blob" or entry[1] not in REGULAR_FILE_MODES:
        raise IndexNavigationError(f"linked index.md is not a regular file: {path}")
    object_id = entry[2]
    size = immutable_object_size(root, object_id)
    if size > MAX_INDEX_BYTES:
        raise IndexNavigationError(
            f"index exceeds {MAX_INDEX_BYTES // 1024} KiB limit: {path}"
        )
    content = immutable_object_content(root, object_id)
    return object_id, parse_index(decode_index_text(content, path), path)


def find_cycle_edges(
    adjacency: dict[str, list[str]],
    root: str,
) -> list[dict[str, str]]:
    cycle_edges: list[dict[str, str]] = []
    cycle_pairs: set[tuple[str, str]] = set()
    visiting: set[str] = {root}
    visited: set[str] = set()
    stack: list[tuple[str, int]] = [(root, 0)]

    while stack:
        node, next_index = stack[-1]
        targets = adjacency.get(node, [])
        if next_index >= len(targets):
            stack.pop()
            visiting.discard(node)
            visited.add(node)
            continue
        target = targets[next_index]
        stack[-1] = (node, next_index + 1)
        if target in visiting:
            pair = (node, target)
            if pair not in cycle_pairs:
                cycle_pairs.add(pair)
                cycle_edges.append({"source": node, "target": target})
            continue
        if target in visited:
            continue
        visiting.add(target)
        stack.append((target, 0))

    return cycle_edges


def read_entries_at_revision(root: Path, revision: str):
    """Read the provider tree at the exact SHA already recorded for provenance."""
    return parse_ls_tree(
        immutable_git(root, "ls-tree", "--full-tree", "-r", "-t", "-z", revision)
    )


def collect_provider_graph(provider: str, root: Path) -> dict[str, object]:
    revision = checked_revision(root)
    entries_list = read_entries_at_revision(root, revision)
    entries: dict[str, tuple[str, str, str]] = {}
    for entry in entries_list:
        try:
            path = entry.path.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            continue
        entries[path] = (entry.kind, entry.mode, entry.object_id)

    root_entry = entries.get(ROOT_INDEX)
    if (
        root_entry is None
        or root_entry[0] != "blob"
        or root_entry[1] not in REGULAR_FILE_MODES
    ):
        raise IndexNavigationError(
            f"{provider} root navigation index must be a regular file: {ROOT_INDEX}"
        )

    queue: deque[tuple[str, int]] = deque([(ROOT_INDEX, 0)])
    seen: set[str] = set()
    queued: set[str] = {ROOT_INDEX}
    indexes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    depths: dict[str, int] = {ROOT_INDEX: 0}
    incoming_sources: dict[str, set[str]] = {}

    while queue:
        path, depth = queue.popleft()
        queued.discard(path)
        if path in seen:
            continue
        seen.add(path)
        object_id, parsed_index = load_reachable_index(root, path, entries.get(path))
        indexes.append(
            {
                "path": path,
                "title": parsed_index.title,
                "sections": [
                    {"title": section.title, "level": section.level}
                    for section in parsed_index.sections
                ],
                "depth": depth,
                "object_id": object_id,
            }
        )
        for link in parsed_index.links:
            resolved = resolve_link(path, link, entries)
            edge = {
                "source": path,
                "section": link.section,
                "label": link.label,
                "description": link.description,
                "line": link.line,
                "raw_target": link.raw_target,
                **resolved,
            }
            edges.append(edge)
            if resolved["kind"] == "index":
                target_path = str(resolved["target"])
                incoming_sources.setdefault(target_path, set()).add(path)
                candidate_depth = depth + 1
                previous = depths.get(target_path)
                if previous is None or candidate_depth < previous:
                    depths[target_path] = candidate_depth
                if target_path not in seen and target_path not in queued:
                    queue.append((target_path, depths[target_path]))
                    queued.add(target_path)

    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge["kind"] == "index":
            adjacency.setdefault(str(edge["source"]), []).append(str(edge["target"]))

    cycle_edges = find_cycle_edges(adjacency, ROOT_INDEX)
    max_depth = max((int(index["depth"]) for index in indexes), default=0)
    return {
        "name": provider,
        "revision": revision,
        "root_index": ROOT_INDEX,
        "indexes": sorted(
            indexes,
            key=lambda value: (int(value["depth"]), str(value["path"])),
        ),
        "edges": edges,
        "diagnostics": {
            "index_count": len(indexes),
            "edge_count": len(edges),
            "max_index_depth": max_depth,
            "cycle_edges": cycle_edges,
            "multiple_parent_indexes": sorted(
                path for path, sources in incoming_sources.items() if len(sources) > 1
            ),
        },
    }


def parse_providers(values: list[str]) -> dict[str, Path]:
    providers: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise IndexNavigationError("provider must use NAME=PATH syntax")
        name, raw_path = value.split("=", maxsplit=1)
        if not raw_path:
            raise IndexNavigationError(f"provider path must not be empty: {name}")
        if name in providers:
            raise IndexNavigationError(f"duplicate provider: {name}")
        providers[name] = Path(raw_path)
    if tuple(providers) != PROVIDER_ORDER:
        raise IndexNavigationError(
            "providers must be supplied exactly in this order: "
            + ", ".join(PROVIDER_ORDER)
        )
    return providers


def generate_graph(repository: str, providers: dict[str, Path]) -> dict[str, object]:
    if not REPOSITORY.fullmatch(repository):
        raise IndexNavigationError("repository must use owner/name syntax")
    if tuple(providers) != PROVIDER_ORDER:
        raise IndexNavigationError(
            "providers must be supplied exactly in this order: "
            + ", ".join(PROVIDER_ORDER)
        )
    graphs = [collect_provider_graph(name, providers[name]) for name in PROVIDER_ORDER]
    for graph in graphs:
        if not FULL_SHA.fullmatch(str(graph["revision"])):
            raise IndexNavigationError("provider revision is not a full lowercase SHA")
    return {
        "schema_version": 1,
        "repository": repository,
        "providers": graphs,
    }


def write_graph(output: Path, graph: dict[str, object]) -> None:
    if output.is_symlink():
        raise IndexNavigationError("output must not be a symlink")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise IndexNavigationError(
            f"unable to write navigation graph output {output}: {exc}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider", action="append", default=[])
    args = parser.parse_args()
    try:
        providers = parse_providers(args.provider)
        graph = generate_graph(args.repository, providers)
        write_graph(args.output, graph)
        for provider in graph["providers"]:
            diagnostics = provider["diagnostics"]
            print(
                f"{provider['name']} index navigation: "
                f"{diagnostics['index_count']} indexes, "
                f"{diagnostics['edge_count']} links, "
                f"depth {diagnostics['max_index_depth']} @ {provider['revision']}"
            )
    except (IndexNavigationError, RepositoryTreeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
