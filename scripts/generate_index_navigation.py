#!/usr/bin/env python3
"""Generate a deterministic navigation graph from provider-owned index.md files."""

from __future__ import annotations

import argparse
import html
import html.entities
import idna
import ipaddress
import json
import os
import posixpath
import re
import string
import subprocess
import unicodedata
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import SplitResult, quote, unquote_to_bytes, urlsplit, urlunsplit

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
CONTEXTUAL_JOINERS = frozenset({"\u200c", "\u200d"})
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
CLOSING_ATX = re.compile(r"[ \t]+#+[ \t]*$")
FORBIDDEN_DOMAIN_CHARACTERS = frozenset("#/:<>?@[\\]^|%")
IPV4_NUMBER = re.compile(r"\A(?:0[xX][0-9A-Fa-f]*|0[0-7]*|[0-9]+)\Z")
COMMONMARK_CHARACTER_REFERENCE = re.compile(
    r"&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});"
)
COMMONMARK_URI_AUTOLINK = re.compile(
    r"<[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\x00-\x20<>]*>"
)
COMMONMARK_EMAIL_AUTOLINK = re.compile(
    r"<[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*>"
)
COMMONMARK_HTML_OPEN_TAG = re.compile(
    r"<[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:[^ \t\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*"
    r"[ \t]*/?>"
)
COMMONMARK_HTML_CLOSING_TAG = re.compile(
    r"</[A-Za-z][A-Za-z0-9-]*[ \t]*>"
)
DESCRIPTION_SUFFIX = re.compile(r"^[ \t]+[-–—][ \t]+(.+?)[ \t]*$")
EXTERNAL_AUTHORITY_SAFE = "%:@[]!$&'()*+,;=-._~"
EXTERNAL_PATH_SAFE = "/%:@!$&'()*+,;=-._~"


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
            or character in NON_MARKDOWN_LINE_SEPARATORS
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
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(f"index is not strict UTF-8: {path}") from exc
    if any(separator in text for separator in NON_MARKDOWN_LINE_SEPARATORS):
        raise IndexNavigationError(
            f"index contains a non-Markdown line separator: {path}"
        )
    if contains_disallowed_control(text):
        raise IndexNavigationError(
            f"index contains a disallowed control character: {path}"
        )
    return text


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


def normalize_heading_value(value: str) -> str:
    """Normalize the human-rendered CommonMark text of an ATX heading."""
    trimmed = value.strip(" \t")
    if trimmed and all(character == "#" for character in trimmed):
        return ""
    without_closing_marker = CLOSING_ATX.sub("", value).strip(" \t")
    return decode_commonmark_inline_text(without_closing_marker).strip(" \t")


def list_marker_indent_columns(line: str, leading_columns: int = 0) -> int:
    """Return CommonMark indentation columns between a bullet marker and link text."""
    bracket = line.find("[", 1)
    if bracket < 0:
        return 0
    column = leading_columns + 1
    start_column = column
    for character in line[1:bracket]:
        if character == " ":
            column += 1
        elif character == "\t":
            column += 4 - (column % 4)
        else:
            return 0
    return column - start_column


def contains_unescaped_character(value: str, needle: str) -> bool:
    """Return whether a punctuation character occurs outside a backslash escape."""
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
        if character == needle:
            return True
        index += 1
    return False


def contains_unescaped_sequence(value: str, sequence: str) -> bool:
    """Return whether a punctuation sequence begins outside a backslash escape."""
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
        if value.startswith(sequence, index):
            return True
        index += 1
    return False


def commonmark_code_span_closers(value: str) -> dict[int, int]:
    """Map each unescaped backtick run to the end of its next equal-length run."""
    previous_by_length: dict[int, int] = {}
    closers: dict[int, int] = {}
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
        if character != "`":
            index += 1
            continue
        start = index
        while index < len(value) and value[index] == "`":
            index += 1
        run_length = index - start
        previous = previous_by_length.get(run_length)
        if previous is not None:
            closers[previous] = index
        previous_by_length[run_length] = start
    return closers


def contains_commonmark_code_span(value: str) -> bool:
    """Return whether source text contains an unescaped CommonMark code span."""
    return bool(commonmark_code_span_closers(value))


def contains_commonmark_autolink(value: str) -> bool:
    """Return whether source text contains an unescaped URI or email autolink."""
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
        if character != "<":
            index += 1
            continue
        uri = COMMONMARK_URI_AUTOLINK.match(value, index)
        if uri is not None:
            return True
        email = COMMONMARK_EMAIL_AUTOLINK.match(value, index)
        if email is not None:
            return True
        index += 1
    return False


def contains_commonmark_raw_html(value: str) -> bool:
    """Return whether source text contains an unescaped CommonMark raw HTML construct."""
    comment_close = value.rfind("-->")
    processing_close = value.rfind("?>")
    cdata_close = value.rfind("]]>")
    declaration_close = value.rfind(">")
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
        if character != "<":
            index += 1
            continue
        if value.startswith("<!--", index) and comment_close >= index + 4:
            return True
        if value.startswith("<?", index) and processing_close >= index + 2:
            return True
        if value.startswith("<![CDATA[", index) and cdata_close >= index + 9:
            return True
        if (
            value.startswith("<!", index)
            and index + 2 < len(value)
            and value[index + 2].isascii()
            and value[index + 2].isalpha()
            and declaration_close >= index + 3
        ):
            return True
        if COMMONMARK_HTML_OPEN_TAG.match(value, index) is not None:
            return True
        if COMMONMARK_HTML_CLOSING_TAG.match(value, index) is not None:
            return True
        index += 1
    return False


def is_commonmark_whitespace(character: str | None) -> bool:
    """Return CommonMark's Unicode-whitespace classification for one character."""
    if character is None:
        return True
    return character in "\t\n\f\r" or unicodedata.category(character) == "Zs"


def is_commonmark_punctuation(character: str | None) -> bool:
    """Return CommonMark's Unicode punctuation/symbol classification."""
    if character is None:
        return False
    return unicodedata.category(character)[:1] in {"P", "S"}


def contains_commonmark_emphasis(value: str) -> bool:
    """Return whether unescaped delimiter runs can form emphasis or strong emphasis."""
    opener_masks = {"*": 0, "_": 0}
    non_closing_opener_masks = {"*": 0, "_": 0}
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
        if character not in "*_":
            index += 1
            continue

        start = index
        while index < len(value) and value[index] == character:
            index += 1
        run_length = index - start
        previous = value[start - 1] if start else None
        following = value[index] if index < len(value) else None
        previous_whitespace = is_commonmark_whitespace(previous)
        following_whitespace = is_commonmark_whitespace(following)
        previous_punctuation = is_commonmark_punctuation(previous)
        following_punctuation = is_commonmark_punctuation(following)
        left_flanking = (
            not following_whitespace
            and (
                not following_punctuation
                or previous_whitespace
                or previous_punctuation
            )
        )
        right_flanking = (
            not previous_whitespace
            and (
                not previous_punctuation
                or following_whitespace
                or following_punctuation
            )
        )
        if character == "*":
            can_open = left_flanking
            can_close = right_flanking
        else:
            can_open = left_flanking and (
                not right_flanking or previous_punctuation
            )
            can_close = right_flanking and (
                not left_flanking or following_punctuation
            )

        residue = run_length % 3
        if can_close:
            opener_mask = opener_masks[character]
            if opener_mask:
                if residue == 0:
                    return True
                incompatible_residue = (3 - residue) % 3
                compatible_mask = opener_mask & ~(1 << incompatible_residue)
                if compatible_mask:
                    return True
                if (
                    not can_open
                    and non_closing_opener_masks[character]
                    & (1 << incompatible_residue)
                ):
                    return True

        if can_open:
            opener_masks[character] |= 1 << residue
            if not can_close:
                non_closing_opener_masks[character] |= 1 << residue

    return False


def parse_reserved_link_suffix(value: str) -> tuple[str, str] | None:
    """Parse a reserved link destination, optional title, and trailing description."""
    if not value.startswith("("):
        return None

    destination_start = 1
    cursor = destination_start
    outer_close: int | None = None

    if cursor < len(value) and value[cursor] == "<":
        index = cursor + 1
        while index < len(value):
            character = value[index]
            if (
                character == "\\"
                and index + 1 < len(value)
                and value[index + 1] in MARKDOWN_ESCAPABLE
            ):
                index += 2
                continue
            if character == ">":
                destination_end = index + 1
                cursor = destination_end
                break
            index += 1
        else:
            return None
    else:
        depth = 0
        index = cursor
        while index < len(value):
            character = value[index]
            if (
                character == "\\"
                and index + 1 < len(value)
                and value[index + 1] in MARKDOWN_ESCAPABLE
            ):
                index += 2
                continue
            if character in " \t":
                if depth:
                    return None
                destination_end = index
                cursor = index
                break
            if character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    destination_end = index
                    outer_close = index
                    cursor = index
                    break
                depth -= 1
            index += 1
        else:
            return None

    raw_target = value[destination_start:destination_end]

    if outer_close is None:
        separator_start = cursor
        while cursor < len(value) and value[cursor] in " \t":
            cursor += 1
        title_separated = cursor > separator_start
        if cursor >= len(value):
            return None
        if value[cursor] == ")":
            outer_close = cursor
        else:
            if not title_separated:
                return None
            opener = value[cursor]
            closer = {"\"": "\"", "'": "'", "(": ")"}.get(opener)
            if closer is None:
                return None
            cursor += 1
            while cursor < len(value):
                character = value[cursor]
                if (
                    character == "\\"
                    and cursor + 1 < len(value)
                    and value[cursor + 1] in MARKDOWN_ESCAPABLE
                ):
                    cursor += 2
                    continue
                if opener == "(" and character == "(":
                    return None
                if character == closer:
                    cursor += 1
                    break
                cursor += 1
            else:
                return None
            while cursor < len(value) and value[cursor] in " \t":
                cursor += 1
            if cursor >= len(value) or value[cursor] != ")":
                return None
            outer_close = cursor

    description = DESCRIPTION_SUFFIX.fullmatch(value[outer_close + 1 :])
    if description is None:
        return None
    return raw_target, description.group(1)


def parse_reserved_link_entry(
    line: str,
    path: str,
    line_number: int,
    leading_columns: int = 0,
) -> tuple[str, str, str] | None:
    """Parse the reserved link-entry shape with escape-aware balanced label brackets."""
    if not line or line[0] not in "*-":
        return None
    bracket = line.find("[", 1)
    if bracket < 0:
        return None
    marker_indent = list_marker_indent_columns(line, leading_columns)
    if not 1 <= marker_indent <= 4:
        raise IndexNavigationError(
            f"list marker indentation must be 1 to 4 columns in "
            f"{path}:{line_number}"
        )

    depth = 1
    escaped_outer_terminator = False
    label_offset = bracket + 1
    code_span_closers = commonmark_code_span_closers(line[label_offset:])
    index = label_offset
    while index < len(line):
        character = line[index]
        if (
            character == "\\"
            and index + 1 < len(line)
            and line[index + 1] in MARKDOWN_ESCAPABLE
        ):
            if (
                depth == 1
                and line[index + 1] == "]"
                and index + 2 < len(line)
                and line[index + 2] == "("
            ):
                escaped_outer_terminator = True
            index += 2
            continue
        if character == "`":
            code_span_end = code_span_closers.get(index - label_offset)
            if code_span_end is not None:
                index = label_offset + code_span_end
                continue
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                break
        index += 1

    if depth:
        if escaped_outer_terminator:
            raise IndexNavigationError(
                f"escaped link-label terminator in {path}:{line_number}"
            )
        return None
    label_source = line[bracket + 1 : index]
    if contains_commonmark_code_span(label_source):
        raise IndexNavigationError(
            f"unsupported inline code span in link label in {path}:{line_number}"
        )
    if contains_commonmark_emphasis(label_source):
        raise IndexNavigationError(
            f"unsupported emphasis in link label in {path}:{line_number}"
        )
    if contains_commonmark_autolink(label_source):
        raise IndexNavigationError(
            f"unsupported autolink in link label in {path}:{line_number}"
        )
    if contains_commonmark_raw_html(label_source):
        raise IndexNavigationError(
            f"unsupported raw HTML in link label in {path}:{line_number}"
        )
    suffix = parse_reserved_link_suffix(line[index + 1 :])
    if suffix is None:
        return None
    if contains_unescaped_sequence(label_source, "]("):
        raise IndexNavigationError(
            f"nested inline link in link label in {path}:{line_number}"
        )
    raw_target, description = suffix
    return label_source, raw_target, description


def normalize_link_description(value: str, path: str, line_number: int) -> str:
    """Normalize plain inline description text while failing closed on richer Markdown."""
    if contains_commonmark_code_span(value):
        raise IndexNavigationError(
            f"unsupported inline code span in link description in {path}:{line_number}"
        )
    if contains_commonmark_emphasis(value):
        raise IndexNavigationError(
            f"unsupported emphasis in link description in {path}:{line_number}"
        )
    if contains_unescaped_sequence(value, "]("):
        raise IndexNavigationError(
            f"unsupported inline link in link description in {path}:{line_number}"
        )
    if contains_commonmark_autolink(value):
        raise IndexNavigationError(
            f"unsupported autolink in link description in {path}:{line_number}"
        )
    if contains_commonmark_raw_html(value):
        raise IndexNavigationError(
            f"unsupported raw HTML in link description in {path}:{line_number}"
        )
    decoded = decode_commonmark_inline_text(value.strip(" \t")).strip(" \t")
    if contains_disallowed_control(decoded, allow_layout_whitespace=False):
        raise IndexNavigationError(
            f"link description contains a disallowed control character in "
            f"{path}:{line_number}"
        )
    return decoded


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
            heading_source = heading.group(2)
            if contains_commonmark_code_span(heading_source):
                raise IndexNavigationError(
                    f"unsupported inline code span in heading in {path}:{line_number}"
                )
            if contains_commonmark_emphasis(heading_source):
                raise IndexNavigationError(
                    f"unsupported emphasis in heading in {path}:{line_number}"
                )
            if contains_unescaped_sequence(heading_source, "]("):
                raise IndexNavigationError(
                    f"unsupported inline link in heading in {path}:{line_number}"
                )
            if contains_commonmark_autolink(heading_source):
                raise IndexNavigationError(
                    f"unsupported autolink in heading in {path}:{line_number}"
                )
            if contains_commonmark_raw_html(heading_source):
                raise IndexNavigationError(
                    f"unsupported raw HTML in heading in {path}:{line_number}"
                )
            value = normalize_heading_value(heading_source)
            if not value:
                raise IndexNavigationError(f"empty heading in {path}:{line_number}")
            if contains_disallowed_control(value, allow_layout_whitespace=False):
                raise IndexNavigationError(
                    f"heading contains a disallowed control character in "
                    f"{path}:{line_number}"
                )
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

        entry = parse_reserved_link_entry(
            line,
            path,
            line_number,
            leading_columns=len(leading),
        )
        if entry is not None:
            label_source, raw_target_source, description_source = entry
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
            raw_target = raw_target_source.strip(" \t")
            destination_backslashes = len(raw_target) - len(raw_target.rstrip("\\"))
            if destination_backslashes % 2:
                raise IndexNavigationError(
                    f"escaped link-destination terminator in {path}:{line_number}"
                )
            description = normalize_link_description(
                description_source,
                path,
                line_number,
            )
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
        or "%" in decoded
        or any(joiner in decoded for joiner in CONTEXTUAL_JOINERS)
        or any(character.isspace() for character in decoded)
        or contains_disallowed_control(decoded, allow_layout_whitespace=False)
    ):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    return decoded


def validate_ascii_punycode_labels(
    ascii_hostname: str,
    source: str,
    line: int,
    target: str,
) -> None:
    """Reject malformed existing A-labels before accepting an ASCII domain."""
    for label in ascii_hostname.split("."):
        if not label.lower().startswith("xn--"):
            continue
        payload = label[4:]
        if not payload:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        try:
            decoded = payload.encode("ascii").decode("punycode")
            canonical_payload = decoded.encode("punycode").decode("ascii")
        except UnicodeError as exc:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            ) from exc
        if (
            not decoded
            or canonical_payload.lower() != payload.lower()
            or any(joiner in decoded for joiner in CONTEXTUAL_JOINERS)
            or contains_disallowed_control(decoded, allow_layout_whitespace=False)
        ):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )


def validate_whatwg_unicode_labels(
    mapped: str,
    source: str,
    line: int,
    target: str,
) -> list[str]:
    """Apply UTS #46 validity criteria not enforced by mapping alone."""
    labels = mapped.split(".")
    if any(not label for label in labels):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    bidi_domain = any(
        unicodedata.bidirectional(character) in {"R", "AL", "AN"}
        for character in mapped
        if character != "."
    )
    for label in labels:
        if (
            unicodedata.normalize("NFC", label) != label
            or unicodedata.category(label[0]).startswith("M")
            or any(joiner in label for joiner in CONTEXTUAL_JOINERS)
        ):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        if bidi_domain:
            try:
                idna.check_bidi(label, check_ltr=True)
            except idna.IDNAError as exc:
                raise IndexNavigationError(
                    f"malformed external link in {source}:{line}: {target!r}"
                ) from exc
    return labels


def canonicalize_whatwg_domain(
    hostname: str,
    source: str,
    line: int,
    target: str,
) -> str:
    """Map a non-ASCII special-scheme domain with WHATWG-compatible UTS #46 rules."""
    if hostname.isascii():
        return hostname.lower().rstrip(".")
    try:
        mapped = idna.uts46_remap(
            hostname,
            std3_rules=False,
            transitional=False,
        ).rstrip(".")
    except idna.IDNAError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if not mapped:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )

    labels = validate_whatwg_unicode_labels(mapped, source, line, target)
    ascii_labels: list[str] = []
    for label in labels:
        if label.isascii():
            ascii_labels.append(label.lower())
            continue
        try:
            payload = label.encode("punycode").decode("ascii").lower()
        except UnicodeError as exc:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            ) from exc
        ascii_labels.append("xn--" + payload)
    return ".".join(ascii_labels)


def validate_external_location(
    parsed: SplitResult,
    source: str,
    line: int,
    target: str,
) -> None:
    host_port = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    bracketed_host = host_port.startswith("[")
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
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if bracketed_host:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
    else:
        if bracketed_host and not isinstance(address, ipaddress.IPv6Address):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        return
    if validate_browser_ipv4_candidate(hostname, source, line, target):
        return

    ascii_hostname = canonicalize_whatwg_domain(hostname, source, line, target)
    if validate_browser_ipv4_candidate(ascii_hostname, source, line, target):
        return
    validate_ascii_punycode_labels(ascii_hostname, source, line, target)
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
        external_netloc = quote(parsed.netloc, safe=EXTERNAL_AUTHORITY_SAFE)
        external_path = quote(parsed.path, safe=EXTERNAL_PATH_SAFE)
        external_target = urlunsplit(
            (parsed.scheme, external_netloc, external_path, "", "")
        )
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
