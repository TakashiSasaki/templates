#!/usr/bin/env python3
"""Finalize per-page canonical URLs and translation reader UI in generated HTML."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urljoin

from finalize_site_metadata import (
    SiteMetadataError,
    rewrite_canonical_link,
    validate_canonical_url,
)
from site_chrome_locales import (
    SITE_CHROME_LOCALES,
    SiteChromeLocaleError,
    language_label,
    load_site_chrome_locales,
    reader_strings,
    translation_status,
)

HTML_TAG_PATTERN = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
HEAD_CLOSE_PATTERN = re.compile(r"</head\s*>", re.IGNORECASE)
H1_CLOSE_PATTERN = re.compile(r"</h1\s*>", re.IGNORECASE)
ALTERNATE_TAG_PATTERN = re.compile(
    r"<link\b(?=[^>]*\brel\s*=\s*[\"'][^\"']*\balternate\b[^\"']*[\"'])"
    r"(?=[^>]*\bhreflang\s*=)[^>]*>\s*",
    re.IGNORECASE,
)
SWITCHER_MARKER = 'class="translation-switcher"'
LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
PUBLICATION_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class TranslationReaderError(RuntimeError):
    """Raised when translation reader metadata cannot be finalized safely."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationReaderError(f"unable to read translation map {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TranslationReaderError(
                    f"translation map contains duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise TranslationReaderError(f"unable to parse translation map {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TranslationReaderError("translation map must be an object")
    return value


def safe_markdown_destination(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise TranslationReaderError(f"{field} must be a safe Markdown destination")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise TranslationReaderError(f"{field} must be a safe Markdown destination")
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.lower() != ".md":
        raise TranslationReaderError(f"{field} must be a safe Markdown destination")
    return path


def markdown_to_html_path(destination: PurePosixPath) -> PurePosixPath:
    if destination.name == "index.md":
        return destination.with_name("index.html")
    return destination.with_suffix("") / "index.html"


def html_public_url(
    relative_html: PurePosixPath,
    canonical_base: str,
) -> str:
    if relative_html.name == "index.html":
        route = relative_html.parent.as_posix()
        if route == ".":
            route = ""
        elif route:
            route += "/"
    else:
        route = relative_html.as_posix()
    return urljoin(canonical_base, route)


def _attribute_span(tag: str, attribute: str) -> tuple[int, int] | None:
    """Return an exact attribute span without matching text inside quoted values."""
    start = re.match(r"<html\b", tag, re.IGNORECASE)
    if start is None:
        return None
    index = start.end()
    limit = len(tag) - 1
    while index < limit:
        while index < limit and tag[index].isspace():
            index += 1
        if index >= limit or tag[index] in "/>":
            break
        name_start = index
        while index < limit and not tag[index].isspace() and tag[index] not in "=/>":
            index += 1
        name = tag[name_start:index]
        while index < limit and tag[index].isspace():
            index += 1
        if index < limit and tag[index] == "=":
            index += 1
            while index < limit and tag[index].isspace():
                index += 1
            if index < limit and tag[index] in "\"'":
                quote = tag[index]
                index += 1
                while index < limit and tag[index] != quote:
                    index += 1
                if index >= limit:
                    raise TranslationReaderError(
                        "html start tag contains an unterminated attribute"
                    )
                index += 1
            else:
                while (
                    index < limit
                    and not tag[index].isspace()
                    and tag[index] not in "/>"
                ):
                    index += 1
        if name.casefold() == attribute.casefold():
            return name_start, index
    return None


def replace_html_language(source: str, language: str, path: Path) -> str:
    matches = list(HTML_TAG_PATTERN.finditer(source))
    if len(matches) != 1:
        raise TranslationReaderError(
            f"{path}: expected exactly one html start tag, found {len(matches)}"
        )
    tag = matches[0].group(0)
    replacement = f'lang="{html.escape(language, quote=True)}"'
    span = _attribute_span(tag, "lang")
    if span is not None:
        updated_tag = tag[: span[0]] + replacement + tag[span[1] :]
    else:
        before_close = tag[:-1]
        trimmed = before_close.rstrip()
        trailing_space = before_close[len(trimmed) :]
        if trimmed.endswith("/"):
            raise TranslationReaderError(f"{path}: html start tag must not be self-closing")
        updated_tag = f"{trimmed} {replacement}{trailing_space}>"
    return source[: matches[0].start()] + updated_tag + source[matches[0].end() :]


def replace_alternates(
    source: str,
    alternates: list[tuple[str, str]],
    path: Path,
) -> str:
    source = ALTERNATE_TAG_PATTERN.sub("", source)
    head_closes = list(HEAD_CLOSE_PATTERN.finditer(source))
    if len(head_closes) != 1:
        raise TranslationReaderError(
            f"{path}: expected exactly one closing head tag, found {len(head_closes)}"
        )
    seen_languages: set[str] = set()
    links: list[str] = []
    for language, target_url in alternates:
        if language in seen_languages:
            raise TranslationReaderError(
                f"{path}: duplicate alternate language: {language}"
            )
        seen_languages.add(language)
        links.append(
            f'<link rel="alternate" hreflang="{html.escape(language, quote=True)}" '
            f'href="{html.escape(target_url, quote=True)}">\n'
        )
    position = head_closes[0].start()
    return source[:position] + "".join(links) + source[position:]


def publication_label(publication: str) -> str:
    return " ".join(part.capitalize() for part in publication.split("-"))


def switcher_link(label: str, target_url: str, language: str) -> str:
    return (
        f'<a class="translation-switcher__link" '
        f'href="{html.escape(target_url, quote=True)}" '
        f'lang="{html.escape(language, quote=True)}" '
        f'hreflang="{html.escape(language, quote=True)}">'
        f"{html.escape(label)}</a>"
    )


def canonical_switcher_markup(
    publication: str,
    translations: list[tuple[str, str]],
    chrome: dict[str, Any],
) -> str:
    canonical_language = chrome["canonical_language"]
    strings = reader_strings(chrome, canonical_language)
    status = (
        f"{html.escape(publication_label(publication))} · "
        f"{html.escape(strings['canonical_status'])}"
    )
    links = "".join(
        switcher_link(language_label(chrome, language), target_url, language)
        for language, target_url in translations
    )
    return (
        '\n<div class="translation-switcher" role="group" '
        f'aria-label="{html.escape(strings["group_label"], quote=True)}">'
        f'<span class="translation-switcher__status">{status}</span>'
        f'<span class="translation-switcher__links">{links}</span></div>'
    )


def translated_switcher_markup(
    publication: str,
    language: str,
    canonical_url: str,
    chrome: dict[str, Any],
) -> str:
    strings = reader_strings(chrome, language)
    status = (
        f"{html.escape(publication_label(publication))} · "
        f"{html.escape(translation_status(chrome, language))}"
    )
    link = switcher_link(strings["canonical_link"], canonical_url, "en")
    return (
        '\n<div class="translation-switcher" role="group" '
        f'aria-label="{html.escape(strings["group_label"], quote=True)}">'
        f'<span class="translation-switcher__status">{status}</span>'
        f'<span class="translation-switcher__links">{link}</span></div>'
    )


def inject_switcher(source: str, markup: str, path: Path) -> str:
    if SWITCHER_MARKER in source:
        raise TranslationReaderError(f"{path}: translation switcher already exists")
    match = H1_CLOSE_PATTERN.search(source)
    if match is None:
        raise TranslationReaderError(f"{path}: unable to find top-level reader heading")
    return source[: match.end()] + markup + source[match.end() :]


def load_pairs(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    expected_fields = {"schema_version", "canonical_language", "translations"}
    actual_fields = set(data)
    missing_fields = expected_fields - actual_fields
    unsupported_fields = actual_fields - expected_fields
    if missing_fields:
        raise TranslationReaderError(
            "translation map is missing required fields: "
            + ", ".join(sorted(missing_fields))
        )
    if unsupported_fields:
        raise TranslationReaderError(
            "translation map has unsupported fields: "
            + ", ".join(sorted(unsupported_fields))
        )
    version = data["schema_version"]
    if type(version) is not int or version != 1:
        raise TranslationReaderError("translation map schema_version must be integer 1")
    if data["canonical_language"] != "en":
        raise TranslationReaderError("translation map canonical_language must be en")
    entries = data["translations"]
    if not isinstance(entries, list):
        raise TranslationReaderError("translation map translations must be an array")

    result: list[dict[str, Any]] = []
    seen_pairs: set[tuple[PurePosixPath, str]] = set()
    seen_translation: set[PurePosixPath] = set()
    canonical_publications: dict[PurePosixPath, str] = {}
    for index, entry in enumerate(entries):
        field = f"translations[{index}]"
        if not isinstance(entry, dict) or set(entry) != {
            "publication",
            "language",
            "canonical_destination",
            "translation_destination",
        }:
            raise TranslationReaderError(
                f"{field} must contain publication, language, canonical_destination, "
                "and translation_destination"
            )
        publication = entry["publication"]
        language = entry["language"]
        if not isinstance(publication, str) or not PUBLICATION_NAME.fullmatch(publication):
            raise TranslationReaderError(f"{field}.publication must be lowercase kebab-case")
        if (
            not isinstance(language, str)
            or not LANGUAGE_TAG.fullmatch(language)
            or language == "en"
        ):
            raise TranslationReaderError(
                f"{field}.language must be a non-English lowercase language tag"
            )
        canonical = safe_markdown_destination(
            entry["canonical_destination"],
            f"{field}.canonical_destination",
        )
        translation = safe_markdown_destination(
            entry["translation_destination"],
            f"{field}.translation_destination",
        )
        expected_translation = PurePosixPath(language) / canonical
        if translation != expected_translation:
            raise TranslationReaderError(
                f"{field}.translation_destination must be {expected_translation}"
            )
        owner = canonical_publications.setdefault(canonical, publication)
        if owner != publication:
            raise TranslationReaderError(
                f"{field}.canonical_destination is assigned to multiple publications"
            )
        pair_key = (canonical, language)
        if pair_key in seen_pairs or translation in seen_translation:
            raise TranslationReaderError(f"{field} duplicates a translation mapping")
        seen_pairs.add(pair_key)
        seen_translation.add(translation)
        result.append(
            {
                "publication": publication,
                "language": language,
                "canonical": canonical,
                "translation": translation,
            }
        )
    return result


def finalize(
    site_root: Path,
    map_path: Path,
    canonical_base: str,
    chrome_path: Path = SITE_CHROME_LOCALES,
) -> tuple[int, int]:
    canonical_base = validate_canonical_url(canonical_base)
    site_root = site_root.resolve(strict=True)
    pairs = load_pairs(map_path)
    chrome = load_site_chrome_locales(chrome_path)

    html_files = sorted(path for path in site_root.rglob("*.html") if path.is_file())
    if not html_files:
        raise TranslationReaderError(f"no generated HTML files found under {site_root}")

    updates: dict[Path, str] = {}
    for path in html_files:
        relative = PurePosixPath(path.relative_to(site_root).as_posix())
        own_url = html_public_url(relative, canonical_base)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TranslationReaderError(f"unable to read generated HTML {path}: {exc}") from exc
        try:
            updates[path] = rewrite_canonical_link(source, own_url, path)
        except SiteMetadataError as exc:
            raise TranslationReaderError(str(exc)) from exc

    groups: dict[tuple[str, PurePosixPath], list[dict[str, Any]]] = {}
    for pair in pairs:
        groups.setdefault((pair["publication"], pair["canonical"]), []).append(pair)

    resolved_groups: list[
        tuple[Path, str, str, list[tuple[dict[str, Any], Path, str]]]
    ] = []
    for (publication, canonical), group in sorted(
        groups.items(),
        key=lambda item: (item[0][0], item[0][1].as_posix()),
    ):
        canonical_relative = markdown_to_html_path(canonical)
        canonical_path = site_root.joinpath(*canonical_relative.parts)
        if canonical_path not in updates:
            raise TranslationReaderError(
                f"translation mapping references missing generated page: {canonical}"
            )
        canonical_url = html_public_url(canonical_relative, canonical_base)
        translations: list[tuple[dict[str, Any], Path, str]] = []
        for pair in sorted(group, key=lambda item: item["language"]):
            translation_relative = markdown_to_html_path(pair["translation"])
            translation_path = site_root.joinpath(*translation_relative.parts)
            if translation_path not in updates:
                raise TranslationReaderError(
                    "translation mapping references missing generated page: "
                    f"{canonical} -> {pair['translation']}"
                )
            translation_url = html_public_url(translation_relative, canonical_base)
            translations.append((pair, translation_path, translation_url))
        resolved_groups.append(
            (canonical_path, publication, canonical_url, translations)
        )

    for canonical_path, publication, canonical_url, translations in resolved_groups:
        alternates = [("en", canonical_url)] + [
            (pair["language"], translation_url)
            for pair, _, translation_url in translations
        ]
        canonical_source = updates[canonical_path]
        canonical_source = replace_html_language(canonical_source, "en", canonical_path)
        canonical_source = replace_alternates(
            canonical_source,
            alternates,
            canonical_path,
        )
        canonical_source = inject_switcher(
            canonical_source,
            canonical_switcher_markup(
                publication,
                [
                    (pair["language"], translation_url)
                    for pair, _, translation_url in translations
                ],
                chrome,
            ),
            canonical_path,
        )
        updates[canonical_path] = canonical_source

        for pair, translation_path, _ in translations:
            translation_source = updates[translation_path]
            translation_source = replace_html_language(
                translation_source,
                pair["language"],
                translation_path,
            )
            try:
                translation_source = rewrite_canonical_link(
                    translation_source,
                    canonical_url,
                    translation_path,
                )
            except SiteMetadataError as exc:
                raise TranslationReaderError(str(exc)) from exc
            translation_source = replace_alternates(
                translation_source,
                alternates,
                translation_path,
            )
            translation_source = inject_switcher(
                translation_source,
                translated_switcher_markup(
                    publication,
                    pair["language"],
                    canonical_url,
                    chrome,
                ),
                translation_path,
            )
            updates[translation_path] = translation_source

    for path, source in updates.items():
        path.write_text(source, encoding="utf-8")
    return len(html_files), len(pairs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--translation-map", required=True, type=Path)
    parser.add_argument("--canonical-url", required=True)
    parser.add_argument(
        "--site-chrome-locales",
        type=Path,
        default=SITE_CHROME_LOCALES,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        page_count, pair_count = finalize(
            args.site_root,
            args.translation_map,
            args.canonical_url,
            args.site_chrome_locales,
        )
    except (
        OSError,
        TranslationReaderError,
        SiteChromeLocaleError,
        SiteMetadataError,
    ) as exc:
        print(f"finalize_translation_reader.py: {exc}", file=sys.stderr)
        return 1
    print(f"page canonicals finalized: {page_count}")
    print(f"translation switchers finalized: {pair_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
