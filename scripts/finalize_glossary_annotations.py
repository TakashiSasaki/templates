#!/usr/bin/env python3
"""Annotate eligible generated HTML text with stable Glossary links."""

from __future__ import annotations

import argparse
import html
import sys
from html.parser import HTMLParser
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_glossary_viewer import GlossaryViewerError, load_model
from scripts.glossary_annotation import (
    AnnotationIndex,
    GlossaryAnnotationError,
    build_annotation_index,
    find_annotation_matches,
)


class GlossaryAnnotationFinalizeError(RuntimeError):
    """Raised when generated site HTML cannot be annotated safely."""


EXCLUDED_TAGS = {
    "a",
    "button",
    "code",
    "footer",
    "form",
    "header",
    "kbd",
    "math",
    "nav",
    "option",
    "pre",
    "samp",
    "script",
    "style",
    "svg",
    "template",
    "textarea",
}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
EXCLUDED_ROUTE_COMPONENTS = {"files", "glossary", "repository-trees"}
CONTENT_CLASS = "md-content__inner"
RUNTIME_STYLE = '<link rel="stylesheet" href="/stylesheets/glossary-inline.css">'
RUNTIME_SCRIPT = '<script src="/javascripts/glossary-inline.js" defer></script>'


def _class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
    tokens: set[str] = set()
    for name, value in attrs:
        if name == "class" and value:
            tokens.update(value.split())
    return tokens


def _render_annotated_data(
    text: str,
    index: AnnotationIndex,
    *,
    raw_fallback: str | None = None,
) -> tuple[str, int]:
    matches = find_annotation_matches(text, index)
    if not matches:
        return (text if raw_fallback is None else raw_fallback), 0

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        pieces.append(html.escape(text[cursor:match.start], quote=False))
        term_id = html.escape(match.term_id, quote=True)
        pieces.append(
            '<a class="glossary-term" href="/glossary/#'
            + term_id
            + '" data-glossary-id="'
            + term_id
            + '">'
            + html.escape(text[match.start:match.end], quote=False)
            + "</a>"
        )
        cursor = match.end
    pieces.append(html.escape(text[cursor:], quote=False))
    return "".join(pieces), len(matches)


class _ContentClassDetector(HTMLParser):
    """Detect a real content-region class from parsed start-tag attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.found = False

    def _inspect(self, attrs: list[tuple[str, str | None]]) -> None:
        if CONTENT_CLASS in _class_tokens(attrs):
            self.found = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._inspect(attrs)


class _AnnotationParser(HTMLParser):
    def __init__(
        self,
        source: str,
        index: AnnotationIndex,
        *,
        target_main: bool,
    ) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.index = index
        self.target_main = target_main
        self.output: list[str] = []
        self.stack: list[tuple[str, bool, bool]] = []
        self.annotation_count = 0
        self._text_raw: list[str] = []
        self._text_decoded: list[str] = []
        self._line_starts = [0]
        for offset, char in enumerate(source):
            if char == "\n":
                self._line_starts.append(offset + 1)

    def _parent_state(self) -> tuple[bool, bool]:
        if not self.stack:
            return False, False
        _, target, excluded = self.stack[-1]
        return target, excluded

    def _state_for_start(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> tuple[bool, bool]:
        parent_target, parent_excluded = self._parent_state()
        classes = _class_tokens(attrs)
        starts_target = CONTENT_CLASS in classes or (self.target_main and tag == "main")
        target = parent_target or starts_target
        excluded = parent_excluded or tag in EXCLUDED_TAGS or "glossary-term" in classes
        return target, excluded

    def _buffer_text(self, raw: str, decoded: str) -> None:
        self._text_raw.append(raw)
        self._text_decoded.append(decoded)

    def _source_offset(self) -> int:
        line, column = self.getpos()
        if line < 1 or line > len(self._line_starts):
            raise GlossaryAnnotationFinalizeError(
                "HTML parser reported an invalid source position"
            )
        return self._line_starts[line - 1] + column

    def _raw_reference(self, prefix: str, name: str) -> str:
        expected = prefix + name
        start = self._source_offset()
        if not self.source.startswith(expected, start):
            raise GlossaryAnnotationFinalizeError(
                "unable to preserve an HTML character-reference source span"
            )
        end = start + len(expected)
        if end < len(self.source) and self.source[end] == ";":
            end += 1
        return self.source[start:end]

    def _flush_text(self) -> None:
        if not self._text_raw:
            return
        raw = "".join(self._text_raw)
        decoded = "".join(self._text_decoded)
        target, excluded = self._parent_state()
        if target and not excluded:
            rendered, count = _render_annotated_data(
                decoded,
                self.index,
                raw_fallback=raw,
            )
            self.output.append(rendered)
            self.annotation_count += count
        else:
            self.output.append(raw)
        self._text_raw.clear()
        self._text_decoded.clear()

    def finish(self) -> None:
        self._flush_text()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._flush_text()
        self.output.append(self.get_starttag_text())
        if tag not in VOID_TAGS:
            target, excluded = self._state_for_start(tag, attrs)
            self.stack.append((tag, target, excluded))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._flush_text()
        self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        self._flush_text()
        self.output.append(f"</{tag}>")
        if tag in VOID_TAGS:
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self._buffer_text(data, data)

    def handle_entityref(self, name: str) -> None:
        raw = self._raw_reference("&", name)
        self._buffer_text(raw, html.unescape(raw))

    def handle_charref(self, name: str) -> None:
        raw = self._raw_reference("&#", name)
        self._buffer_text(raw, html.unescape(raw))

    def handle_comment(self, data: str) -> None:
        self._flush_text()
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._flush_text()
        self.output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self._flush_text()
        self.output.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self._flush_text()
        self.output.append(f"<![{data}]>")


def _has_content_class(source: str) -> bool:
    detector = _ContentClassDetector()
    detector.feed(source)
    detector.close()
    return detector.found


def annotate_html(source: str, index: AnnotationIndex) -> tuple[str, int]:
    """Annotate one HTML document without changing text outside content regions."""
    try:
        target_main = not _has_content_class(source)
        parser = _AnnotationParser(source, index, target_main=target_main)
        parser.feed(source)
        parser.close()
        parser.finish()
    except GlossaryAnnotationFinalizeError:
        raise
    except (ValueError, TypeError) as exc:
        raise GlossaryAnnotationFinalizeError(f"unable to parse generated HTML: {exc}") from exc
    return "".join(parser.output), parser.annotation_count


def inject_runtime_assets(source: str) -> str:
    """Enhance annotated full documents while preserving static-link fallback."""
    missing = [asset for asset in (RUNTIME_STYLE, RUNTIME_SCRIPT) if asset not in source]
    if not missing:
        return source
    marker = "</head>"
    if marker not in source:
        # Build-time annotation remains useful without JavaScript. Generated Site
        # pages normally contain a head element, while reduced fixtures or other
        # HTML fragments retain the stable Glossary links without enhancement.
        return source
    return source.replace(marker, "\n".join(missing) + "\n" + marker, 1)


def _excluded_route(relative: Path) -> bool:
    return relative.stem in EXCLUDED_ROUTE_COMPONENTS or any(
        part in EXCLUDED_ROUTE_COMPONENTS for part in relative.parts[:-1]
    )


def annotate_site(site_root: Path, glossary_path: Path) -> tuple[int, int]:
    """Annotate eligible HTML files and return ``(files_changed, links_added)``."""
    try:
        root = site_root.resolve(strict=True)
    except OSError as exc:
        raise GlossaryAnnotationFinalizeError(f"unable to resolve site root: {exc}") from exc
    if site_root.is_symlink() or not root.is_dir():
        raise GlossaryAnnotationFinalizeError("site root must be a regular directory")

    try:
        model = load_model(glossary_path)
        index = build_annotation_index(model)
    except (GlossaryViewerError, GlossaryAnnotationError) as exc:
        raise GlossaryAnnotationFinalizeError(
            f"unable to prepare Glossary annotation data: {exc}"
        ) from exc

    files_changed = 0
    links_added = 0
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root)
        if _excluded_route(relative):
            continue
        if path.is_symlink() or not path.is_file():
            raise GlossaryAnnotationFinalizeError(
                f"generated HTML must be a regular file: {relative.as_posix()}"
            )
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise GlossaryAnnotationFinalizeError(
                f"unable to read generated HTML {relative.as_posix()}: {exc}"
            ) from exc
        rendered, count = annotate_html(source, index)
        if count > 0 or 'class="glossary-term"' in rendered:
            rendered = inject_runtime_assets(rendered)
        if rendered == source:
            continue
        try:
            path.write_text(rendered, encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise GlossaryAnnotationFinalizeError(
                f"unable to write generated HTML {relative.as_posix()}: {exc}"
            ) from exc
        files_changed += 1
        links_added += count

    if index.ambiguous:
        labels = ", ".join(sorted(index.ambiguous))
        print(
            "finalize_glossary_annotations.py: skipped ambiguous labels: " + labels,
            file=sys.stderr,
        )
    return files_changed, links_added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--glossary", required=True, type=Path)
    args = parser.parse_args()
    try:
        files_changed, links_added = annotate_site(args.site_root, args.glossary)
    except GlossaryAnnotationFinalizeError as exc:
        print(f"finalize_glossary_annotations.py: {exc}", file=sys.stderr)
        return 1
    print(
        f"Annotated {files_changed} HTML files with {links_added} Glossary links."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
