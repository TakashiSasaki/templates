#!/usr/bin/env python3
"""Apply site-owned reader metadata to generated translation Markdown."""

from __future__ import annotations

import re
from pathlib import Path

TOP_LEVEL_SEARCH = re.compile(r"^search\s*:", re.MULTILINE)


class TranslationReaderMetadataError(RuntimeError):
    """Raised when generated translation metadata cannot be merged safely."""


def exclude_translation_from_search(path: Path) -> None:
    """Add search exclusion without changing provider-owned translation sources."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationReaderMetadataError(
            f"unable to read generated translation {path}: {exc}"
        ) from exc

    metadata = "search:\n  exclude: true\n"
    if text.startswith("---\n") or text.startswith("---\r\n"):
        lines = text.splitlines(keepends=True)
        closing = None
        for index, line in enumerate(lines[1:], start=1):
            if line.rstrip("\r\n") == "---":
                closing = index
                break
        if closing is None:
            raise TranslationReaderMetadataError(
                f"generated translation has unterminated front matter: {path}"
            )
        existing = "".join(lines[1:closing])
        if TOP_LEVEL_SEARCH.search(existing):
            raise TranslationReaderMetadataError(
                f"generated translation already defines top-level search metadata: {path}"
            )
        lines.insert(closing, metadata)
        rendered = "".join(lines)
    else:
        rendered = f"---\n{metadata}---\n\n{text}"

    path.write_text(rendered, encoding="utf-8")
