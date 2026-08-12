#!/usr/bin/env python3
"""Public entry point for deterministic provider-owned index navigation.

The reviewed implementation is preserved in ``generate_index_navigation_base``.
This module applies the description-level CommonMark compatibility layer needed by
provider ``index.md`` files, then re-exports the implementation API unchanged.
"""

from __future__ import annotations

try:
    from scripts import generate_index_navigation_base as _base
except ModuleNotFoundError:
    import generate_index_navigation_base as _base

# Re-export the preserved implementation without relying on package import mode.
for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def _backtick_run_length(value: str, start: int) -> int:
    end = start
    while end < len(value) and value[end] == "`":
        end += 1
    return end - start


def _is_escaped_backtick_opener(value: str, start: int) -> bool:
    backslashes = 0
    cursor = start - 1
    while cursor >= 0 and value[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def commonmark_code_span_closers(value: str) -> dict[int, int]:
    """Map code-span openers to closers without producing overlapping spans.

    CommonMark chooses a backtick opener and then the next raw run of exactly the
    same length. Runs of another length inside that open span are literal code
    content and cannot become independent openers.
    """
    closers: dict[int, int] = {}
    index = 0
    while index < len(value):
        if value[index] != "`":
            index += 1
            continue

        opener = index
        run_length = _backtick_run_length(value, opener)
        index += run_length
        if _is_escaped_backtick_opener(value, opener):
            continue

        cursor = index
        while cursor < len(value):
            if value[cursor] != "`":
                cursor += 1
                continue
            candidate_length = _backtick_run_length(value, cursor)
            candidate_end = cursor + candidate_length
            if candidate_length == run_length:
                closers[opener] = candidate_end
                index = candidate_end
                break
            cursor = candidate_end
        else:
            index = opener + run_length

    return closers


def contains_commonmark_code_span(value: str) -> bool:
    return bool(commonmark_code_span_closers(value))


def commonmark_code_span_run_length(value: str, opener: int) -> int:
    return _backtick_run_length(value, opener)


def mask_commonmark_code_span_contents(value: str) -> str:
    """Mask only the literal contents of sequential, non-overlapping code spans."""
    masked = list(value)
    for opener, end in commonmark_code_span_closers(value).items():
        run_length = _backtick_run_length(value, opener)
        for position in range(opener + run_length, end - run_length):
            masked[position] = "x"
    return "".join(masked)


def decode_commonmark_inline_text_with_code_spans(value: str) -> str:
    """Render plain inline text while preserving CommonMark code-span semantics."""
    closers = commonmark_code_span_closers(value)
    decoded_parts: list[str] = []
    cursor = 0
    index = 0
    while index < len(value):
        code_span_end = closers.get(index)
        if code_span_end is None:
            index += 1
            continue

        decoded_parts.append(_base.decode_commonmark_inline_text(value[cursor:index]))
        run_length = _backtick_run_length(value, index)
        code = value[index + run_length : code_span_end - run_length]
        code = code.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        if code.startswith(" ") and code.endswith(" ") and code.strip(" "):
            code = code[1:-1]
        decoded_parts.append(code)
        cursor = code_span_end
        index = code_span_end

    decoded_parts.append(_base.decode_commonmark_inline_text(value[cursor:]))
    return "".join(decoded_parts)


def contains_commonmark_inline_link(value: str) -> bool:
    """Detect complete inline links/images while honoring code-span precedence."""
    code_span_closers = commonmark_code_span_closers(value)
    parenthesis_closers = _base.commonmark_parenthesis_closers(value)
    parenthesis_depths = _base.commonmark_parenthesis_depths(value)
    next_layout_whitespace = _base.next_layout_whitespace_positions(value)
    close_positions = _base.unescaped_closing_parentheses(value)
    last_close = max(close_positions, default=-1)
    last_layout_whitespace = max(value.rfind(" "), value.rfind("\t"))
    bracket_depth = 0
    index = 0
    while index < len(value):
        character = value[index]
        if (
            character == "\\"
            and index + 1 < len(value)
            and value[index + 1] in _base.MARKDOWN_ESCAPABLE
        ):
            index += 2
            continue
        if character == "`" and bracket_depth == 0:
            code_span_end = code_span_closers.get(index)
            if code_span_end is not None:
                index = code_span_end
                continue
        if character == "[":
            bracket_depth += 1
        elif character == "]" and bracket_depth:
            bracket_depth -= 1
            candidate_open = index + 1
            if value.startswith("(", candidate_open):
                pointy = (
                    candidate_open + 1 < len(value)
                    and value[candidate_open + 1] == "<"
                )
                outer_close = parenthesis_closers.get(candidate_open)
                if not pointy and outer_close is not None:
                    whitespace = next_layout_whitespace[candidate_open + 1]
                    if whitespace >= outer_close:
                        return True
                    base_depth = parenthesis_depths[candidate_open + 1]
                    if parenthesis_depths[whitespace] > base_depth:
                        index += 1
                        continue
                if not pointy and outer_close is None:
                    if (
                        last_layout_whitespace <= candidate_open
                        or last_close <= candidate_open
                    ):
                        index += 1
                        continue
                if pointy and last_close <= candidate_open:
                    index += 1
                    continue
                if _base.parse_commonmark_inline_destination(
                    value[candidate_open:]
                ) is not None:
                    return True
        index += 1
    return False


def contains_commonmark_autolink(value: str) -> bool:
    """Detect URI/email autolinks outside literal code spans."""
    code_span_closers = commonmark_code_span_closers(value)
    index = 0
    while index < len(value):
        character = value[index]
        if (
            character == "\\"
            and index + 1 < len(value)
            and value[index + 1] in _base.MARKDOWN_ESCAPABLE
        ):
            index += 2
            continue
        if character == "`":
            code_span_end = code_span_closers.get(index)
            if code_span_end is not None:
                index = code_span_end
                continue
        if character != "<":
            index += 1
            continue
        if _base.COMMONMARK_URI_AUTOLINK.match(value, index) is not None:
            return True
        if _base.COMMONMARK_EMAIL_AUTOLINK.match(value, index) is not None:
            return True
        index += 1
    return False


def contains_commonmark_raw_html(value: str) -> bool:
    """Detect raw HTML outside literal code spans."""
    code_span_closers = commonmark_code_span_closers(value)
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
            and value[index + 1] in _base.MARKDOWN_ESCAPABLE
        ):
            index += 2
            continue
        if character == "`":
            code_span_end = code_span_closers.get(index)
            if code_span_end is not None:
                index = code_span_end
                continue
        if character != "<":
            index += 1
            continue
        if value.startswith(("<!-->", "<!--->"), index):
            return True
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
        if _base.COMMONMARK_HTML_OPEN_TAG.match(value, index) is not None:
            return True
        if _base.COMMONMARK_HTML_CLOSING_TAG.match(value, index) is not None:
            return True
        index += 1
    return False


def contains_commonmark_emphasis(value: str) -> bool:
    """Detect emphasis outside code, without letting later code hide an opener."""
    code_span_closers = commonmark_code_span_closers(value)
    opener_masks = {"*": 0, "_": 0}
    non_closing_opener_masks = {"*": 0, "_": 0}
    index = 0
    while index < len(value):
        character = value[index]
        if (
            character == "\\"
            and index + 1 < len(value)
            and value[index + 1] in _base.MARKDOWN_ESCAPABLE
        ):
            index += 2
            continue
        if character == "`" and not any(opener_masks.values()):
            code_span_end = code_span_closers.get(index)
            if code_span_end is not None:
                index = code_span_end
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
        previous_whitespace = _base.is_commonmark_whitespace(previous)
        following_whitespace = _base.is_commonmark_whitespace(following)
        previous_punctuation = _base.is_commonmark_punctuation(previous)
        following_punctuation = _base.is_commonmark_punctuation(following)
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


def normalize_link_description(value: str, path: str, line_number: int) -> str:
    """Normalize plain text plus code spans, rejecting richer Markdown outside code."""
    if contains_commonmark_emphasis(value):
        raise _base.IndexNavigationError(
            f"unsupported emphasis in link description in {path}:{line_number}"
        )
    if contains_commonmark_inline_link(value):
        raise _base.IndexNavigationError(
            f"unsupported inline link in link description in {path}:{line_number}"
        )
    if contains_commonmark_autolink(value):
        raise _base.IndexNavigationError(
            f"unsupported autolink in link description in {path}:{line_number}"
        )
    if contains_commonmark_raw_html(value):
        raise _base.IndexNavigationError(
            f"unsupported raw HTML in link description in {path}:{line_number}"
        )
    decoded = decode_commonmark_inline_text_with_code_spans(value.strip(" \t"))
    if _base.contains_disallowed_control(decoded, allow_layout_whitespace=False):
        raise _base.IndexNavigationError(
            f"link description contains a disallowed control character in "
            f"{path}:{line_number}"
        )
    normalized = decoded.strip(" \t")
    if not normalized:
        raise _base.IndexNavigationError(
            f"empty link description in {path}:{line_number}"
        )
    return normalized


# Patch the preserved implementation's module globals. Functions such as
# parse_index() resolve these names in that module at call time, so all callers
# (imports and the CLI) receive the corrected behavior without duplicating the
# large reviewed implementation.
_base.commonmark_code_span_closers = commonmark_code_span_closers
_base.contains_commonmark_code_span = contains_commonmark_code_span
_base.commonmark_code_span_run_length = commonmark_code_span_run_length
_base.mask_commonmark_code_span_contents = mask_commonmark_code_span_contents
_base.decode_commonmark_inline_text_with_code_spans = decode_commonmark_inline_text_with_code_spans
_base.contains_commonmark_inline_link = contains_commonmark_inline_link
_base.contains_commonmark_autolink = contains_commonmark_autolink
_base.contains_commonmark_raw_html = contains_commonmark_raw_html
_base.contains_commonmark_emphasis = contains_commonmark_emphasis
_base.normalize_link_description = normalize_link_description


def main() -> int:
    return _base.main()


if __name__ == "__main__":
    raise SystemExit(main())
