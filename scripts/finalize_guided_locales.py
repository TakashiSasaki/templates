#!/usr/bin/env python3
"""Finalize canonical metadata and language switchers for localized guided pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

try:
    from scripts.finalize_site_metadata import (
        BODY_CLOSE_PATTERN,
        GUIDED_COPY_SCRIPT_TAG,
        SiteMetadataError,
        allow_guided_copy_script,
        discover_page_path_routes,
        ensure_pwa_metadata,
        generated_html_files,
        guided_copy_button,
        render_page_path_breadcrumb,
        rewrite_canonical_link,
        validate_canonical_url,
        validate_github_source_url,
    )
    from scripts.finalize_translation_reader import (
        TranslationReaderError,
        html_public_url,
        inject_switcher,
        replace_alternates,
        replace_html_language,
    )
except ModuleNotFoundError:
    from finalize_site_metadata import (
        BODY_CLOSE_PATTERN,
        GUIDED_COPY_SCRIPT_TAG,
        SiteMetadataError,
        allow_guided_copy_script,
        discover_page_path_routes,
        ensure_pwa_metadata,
        generated_html_files,
        guided_copy_button,
        render_page_path_breadcrumb,
        rewrite_canonical_link,
        validate_canonical_url,
        validate_github_source_url,
    )
    from finalize_translation_reader import (
        TranslationReaderError,
        html_public_url,
        inject_switcher,
        replace_alternates,
        replace_html_language,
    )

HEAD_CLOSE = re.compile(r"</head\s*>", re.IGNORECASE)
LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
GUIDED_LANGUAGE_LABELS = {
    "ja": "日本語",
}
LOCALIZED_PAGE_PATH_PATTERN = re.compile(
    r'<p class="page-path"><span class="page-path-label">(?P<label>[^<]+)</span>\s*'
    r'<code>(?P<path>[^<]+)</code></p>'
)
LOCALIZED_IMMUTABLE_GITHUB_SOURCE_PATTERN = re.compile(
    r'<a\b[^>]*\bhref="(?P<href>[^"]+)"[^>]*>\s*'
    r'(?:immutable GitHub source|不変の GitHub ソース)\s*</a>',
    re.IGNORECASE,
)
STYLE_MARKER = 'id="guided-translation-reader-style"'
STYLE = """<style id="guided-translation-reader-style">
.translation-switcher{display:flex;align-items:center;justify-content:space-between;gap:.75rem;margin:.55rem 0 1rem;padding:.5rem .65rem;border:1px solid #d7dce5;border-radius:.65rem;background:#f8f9fb;font-size:.88rem;line-height:1.35}.translation-switcher__status{color:#505866}.translation-switcher__links{display:flex;flex-wrap:wrap;gap:.35rem}.translation-switcher__link{display:inline-block;padding:.3rem .55rem;border:1px solid #b7c0d0;border-radius:999px;background:#fff;text-decoration:none;font-weight:650}@media(max-width:600px){.translation-switcher{align-items:flex-start;flex-direction:column;gap:.4rem;padding:.45rem .55rem;margin:.45rem 0 .8rem}.translation-switcher__link{padding:.25rem .5rem}}
</style>
"""


class GuidedLocaleFinalizeError(RuntimeError):
    """Raised when localized guided page metadata is malformed or ambiguous."""


def guided_language_label(language: str) -> str:
    primary = language.split("-", 1)[0]
    return GUIDED_LANGUAGE_LABELS.get(primary, language)


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GuidedLocaleFinalizeError(f"guided locale pair map must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GuidedLocaleFinalizeError(f"unable to read guided locale pair map: {exc}") from exc
    if not isinstance(value, dict):
        raise GuidedLocaleFinalizeError("guided locale pair map must be an object")
    return value


def safe_html_path(value: Any, field: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
        raise GuidedLocaleFinalizeError(f"{field} must be a safe relative HTML path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise GuidedLocaleFinalizeError(f"{field} must be a safe relative HTML path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.lower() != ".html":
        raise GuidedLocaleFinalizeError(f"{field} must be a safe relative HTML path")
    return path


def encoded_html_public_url(relative: PurePosixPath, canonical_base: str) -> str:
    """Return a public URL whose filesystem path components are percent-encoded."""
    encoded = PurePosixPath(*(quote(part, safe="") for part in relative.parts))
    return html_public_url(encoded, canonical_base)


def load_pairs(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if set(data) != {"schema_version", "canonical_language", "pages"}:
        raise GuidedLocaleFinalizeError("guided locale pair map has unsupported fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise GuidedLocaleFinalizeError("guided locale pair map schema_version must be integer 1")
    if data["canonical_language"] != "en" or not isinstance(data["pages"], list):
        raise GuidedLocaleFinalizeError("guided locale pair map is invalid")
    pairs: list[dict[str, Any]] = []
    seen_translations: set[PurePosixPath] = set()
    seen_pair: set[tuple[PurePosixPath, str]] = set()
    for index, record in enumerate(data["pages"]):
        field = f"pages[{index}]"
        if not isinstance(record, dict) or set(record) != {
            "language",
            "canonical_path",
            "translation_path",
        }:
            raise GuidedLocaleFinalizeError(f"{field} has unsupported fields")
        language = record["language"]
        if (
            not isinstance(language, str)
            or not LANGUAGE_TAG.fullmatch(language)
            or language == "en"
        ):
            raise GuidedLocaleFinalizeError(f"{field}.language is invalid")
        canonical = safe_html_path(record["canonical_path"], f"{field}.canonical_path")
        translation = safe_html_path(record["translation_path"], f"{field}.translation_path")
        if canonical.parts[0] != "guided":
            raise GuidedLocaleFinalizeError(f"{field}.canonical_path must be under guided/")
        if translation.parts[:2] != (language, "guided"):
            raise GuidedLocaleFinalizeError(
                f"{field}.translation_path must be under {language}/guided/"
            )
        if translation.parts[2:] != canonical.parts[1:]:
            raise GuidedLocaleFinalizeError(f"{field} localized path must mirror canonical guided path")
        key = (canonical, language)
        if key in seen_pair or translation in seen_translations:
            raise GuidedLocaleFinalizeError(f"{field} duplicates a guided locale mapping")
        seen_pair.add(key)
        seen_translations.add(translation)
        pairs.append({"language": language, "canonical": canonical, "translation": translation})
    return pairs


def existing_html(site_root: Path, relative: PurePosixPath, field: str) -> Path:
    root = site_root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise GuidedLocaleFinalizeError(f"{field} must not traverse a symlink: {relative}")
    if not current.is_file():
        raise GuidedLocaleFinalizeError(f"{field} is missing generated HTML: {relative}")
    return current


def switch_link(label: str, target: str, language: str) -> str:
    return (
        f'<a class="translation-switcher__link" href="{html.escape(target, quote=True)}" '
        f'lang="{html.escape(language, quote=True)}" hreflang="{html.escape(language, quote=True)}">'
        f"{html.escape(label)}</a>"
    )


def canonical_markup(translations: list[tuple[str, str]]) -> str:
    links = "".join(
        switch_link(guided_language_label(language), target, language)
        for language, target in translations
    )
    return (
        '\n<div class="translation-switcher" role="group" aria-label="Navigation language">'
        '<span class="translation-switcher__status">Site · Canonical English</span>'
        f'<span class="translation-switcher__links">{links}</span></div>'
    )


def translated_markup(language: str, canonical_url: str) -> str:
    status = (
        "Site · 日本語参考表示"
        if language.split("-", 1)[0] == "ja"
        else f"Site · {guided_language_label(language)} localized view · Non-authoritative"
    )
    return (
        '\n<div class="translation-switcher" role="group" aria-label="Navigation language">'
        f'<span class="translation-switcher__status">{html.escape(status)}</span>'
        '<span class="translation-switcher__links">'
        f'{switch_link("English · Canonical", canonical_url, "en")}'
        "</span></div>"
    )


def add_style(source: str, path: Path) -> str:
    if STYLE_MARKER in source:
        return source
    matches = list(HEAD_CLOSE.finditer(source))
    if len(matches) != 1:
        raise GuidedLocaleFinalizeError(
            f"{path}: expected exactly one closing head tag, found {len(matches)}"
        )
    position = matches[0].start()
    return source[:position] + STYLE + source[position:]


def validate_localized_guided_page_path(value: str, language: str, path: Path) -> str:
    parsed = urlsplit(value)
    prefix = f"/{language}/guided/"
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not value.startswith(prefix)
        or not value.endswith("/")
        or "\\" in value
        or "//" in value[1:]
    ):
        raise GuidedLocaleFinalizeError(
            f"{path}: invalid localized guided page path: {value!r}"
        )
    return value


def enhance_localized_guided_copy_controls(
    source: str,
    canonical_base: str,
    language: str,
    path: Path,
    page_routes: set[str] | None = None,
) -> str:
    """Apply the canonical guided copy-control contract to one localized page."""
    page_path_matches = list(LOCALIZED_PAGE_PATH_PATTERN.finditer(source))
    if not page_path_matches:
        return source
    if len(page_path_matches) != 1:
        raise GuidedLocaleFinalizeError(f"{path}: multiple localized guided page path markers")

    page_path_match = page_path_matches[0]
    page_path = validate_localized_guided_page_path(
        html.unescape(page_path_match.group("path")), language, path
    )
    if page_routes is None:
        page_routes = {page_path}
    if page_path not in page_routes:
        raise GuidedLocaleFinalizeError(
            f"{path}: localized guided page path is not declared by a generated page: {page_path!r}"
        )
    public_url = urljoin(canonical_base, page_path.lstrip("/"))

    github_matches = list(LOCALIZED_IMMUTABLE_GITHUB_SOURCE_PATTERN.finditer(source))
    if len(github_matches) > 1:
        raise GuidedLocaleFinalizeError(f"{path}: multiple immutable GitHub sources")

    buttons: list[str] = []
    if github_matches:
        github_url = validate_github_source_url(
            html.unescape(github_matches[0].group("href")), path
        )
        buttons.append(guided_copy_button("GitHub URL", github_url))
    buttons.append(guided_copy_button("public URL", public_url))

    label = html.unescape(page_path_match.group("label"))
    replacement = (
        f'<nav class="page-path" aria-label="{html.escape(label, quote=True)}">'
        '<span class="page-path-label">'
        f"{html.escape(label)}"
        "</span> "
        f'<code>{render_page_path_breadcrumb(page_path, page_routes)}</code> '
        '<span class="page-path-actions">'
        + " ".join(buttons)
        + ' <span class="copy-status" role="status" aria-live="polite"></span>'
        "</span></nav>"
    )
    updated = source[: page_path_match.start()] + replacement + source[page_path_match.end() :]
    updated = allow_guided_copy_script(updated, path)

    if GUIDED_COPY_SCRIPT_TAG not in updated:
        body_closes = list(BODY_CLOSE_PATTERN.finditer(updated))
        if len(body_closes) != 1:
            raise GuidedLocaleFinalizeError(
                f"{path}: expected exactly one closing body tag, found {len(body_closes)}"
            )
        position = body_closes[0].start()
        updated = updated[:position] + GUIDED_COPY_SCRIPT_TAG + "\n" + updated[position:]
    return updated


def finalize(
    site_root: Path,
    pair_map: Path,
    canonical_base: str,
) -> list[str]:
    canonical_base = validate_canonical_url(canonical_base)
    pairs = load_pairs(pair_map)
    _resolved_root, html_files = generated_html_files(site_root)
    page_routes = discover_page_path_routes(html_files)
    groups: dict[PurePosixPath, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        groups[pair["canonical"]].append(pair)

    updates: dict[Path, str] = {}
    messages: list[str] = []
    for canonical, records in groups.items():
        canonical_file = existing_html(site_root, canonical, "canonical guided page")
        canonical_url = encoded_html_public_url(canonical, canonical_base)

        resolved: list[tuple[dict[str, Any], Path, str]] = []
        for record in sorted(records, key=lambda value: value["language"]):
            translation_file = existing_html(
                site_root,
                record["translation"],
                "localized guided page",
            )
            translation_url = encoded_html_public_url(
                record["translation"],
                canonical_base,
            )
            resolved.append((record, translation_file, translation_url))

        translated_urls = [
            (record["language"], translation_url)
            for record, _translation_file, translation_url in resolved
        ]
        alternates = [("en", canonical_url), *translated_urls]

        for record, translation_file, _translation_url in resolved:
            source = translation_file.read_text(encoding="utf-8")
            source = enhance_localized_guided_copy_controls(
                source,
                canonical_base,
                record["language"],
                translation_file,
                page_routes,
            )
            source = ensure_pwa_metadata(source, translation_file)
            source = rewrite_canonical_link(source, canonical_url, translation_file)
            source = replace_alternates(source, alternates, translation_file)
            source = replace_html_language(source, record["language"], translation_file)
            source = inject_switcher(
                source,
                translated_markup(record["language"], canonical_url),
                translation_file,
            )
            source = add_style(source, translation_file)
            updates[translation_file] = source

        source = canonical_file.read_text(encoding="utf-8")
        source = ensure_pwa_metadata(source, canonical_file)
        source = rewrite_canonical_link(source, canonical_url, canonical_file)
        source = replace_alternates(source, alternates, canonical_file)
        source = replace_html_language(source, "en", canonical_file)
        source = inject_switcher(
            source,
            canonical_markup(translated_urls),
            canonical_file,
        )
        source = add_style(source, canonical_file)
        updates[canonical_file] = source
        messages.append(
            f"guided locale group finalized: {canonical.as_posix()} ({len(records)} translation(s))"
        )

    for path, content in updates.items():
        path.write_text(content, encoding="utf-8")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--pair-map", required=True, type=Path)
    parser.add_argument("--canonical-url", required=True)
    args = parser.parse_args()
    try:
        messages = finalize(args.site_root, args.pair_map, args.canonical_url)
    except (
        GuidedLocaleFinalizeError,
        SiteMetadataError,
        TranslationReaderError,
        OSError,
        UnicodeError,
    ) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
