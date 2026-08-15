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
    "nav",
    "pre",
    "samp",
    "script",
    "style",
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


def _render_annotated_data(text: str, index: AnnotationIndex) -> tuple[str, int]:
    matches = find_annotation_matches(text, index)
    if not matches:
        return text, 0

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        pieces.append(text[cursor:match.start])
        term_id = html.escape(match.term_id, quote=True)
        pieces.append(
            '<a class="glossary-term" href="/glossary/#'
            + term_id
            + '" data-glossary-id="'
            + term_id
            + '">'
            + text[match.start:match.end]
            + "</a>"
        )
        cursor = match.end
    pieces.append(text[cursor:])
    return "".join(pieces), len(matches)


class _AnnotationParser(HTMLParser):
    def __init__(self, index: AnnotationIndex, *, target_main: bool) -> None:
        super().__init__(convert_charrefs=False)
        self.index = index
        self.target_main = target_main
        self.output: list[str] = []
        self.stack: list[tuple[bool, bool]] = []
        self.annotation_count = 0

    def _parent_state(self) -> tuple[bool, bool]:
        if not self.stack:
            return False, False
        return self.stack[-1]

    @staticmethod
    def _class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
        tokens: set[str] = set()
        for name, value in attrs:
            if name == "class" and value:
                tokens.update(value.split())
        return tokens

    def _state_for_start(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> tuple[bool, bool]:
        parent_target, parent_excluded = self._parent_state()
        classes = self._class_tokens(attrs)
        starts_target = CONTENT_CLASS in classes or (self.target_main and tag == "main")
        target = parent_target or starts_target
        excluded = parent_excluded or tag in EXCLUDED_TAGS or "glossary-term" in classes
        return target, excluded

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(self.get_starttag_text())
        if tag not in VOID_TAGS:
            self.stack.append(self._state_for_start(tag, attrs))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        self.output.append(f"</{tag}>")
        if tag not in VOID_TAGS and self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        target, excluded = self._parent_state()
        if target and not excluded:
            rendered, count = _render_annotated_data(data, self.index)
            self.output.append(rendered)
            self.annotation_count += count
        else:
            self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.output.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self.output.append(f"<![{data}]>")


def annotate_html(source: str, index: AnnotationIndex) -> tuple[str, int]:
    """Annotate one HTML document without changing text outside content regions."""
    target_main = CONTENT_CLASS not in source
    parser = _AnnotationParser(index, target_main=target_main)
    try:
        parser.feed(source)
        parser.close()
    except (ValueError, TypeError) as exc:
        raise GlossaryAnnotationFinalizeError(f"unable to parse generated HTML: {exc}") from exc
    return "".join(parser.output), parser.annotation_count


def _excluded_route(relative: Path) -> bool:
    return any(part in EXCLUDED_ROUTE_COMPONENTS for part in relative.parts[:-1])


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
        if count == 0:
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
        parser.error(str(exc))
    print(
        f"Annotated {files_changed} HTML files with {links_added} Glossary links."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
