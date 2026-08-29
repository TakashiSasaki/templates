#!/usr/bin/env python3
"""Validate final reader translation pairs in a generated documentation site."""

from __future__ import annotations

import argparse
import html.parser
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit


LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
PUBLICATION_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class TranslationPairValidationError(RuntimeError):
    """Raised when generated reader translation pairs are inconsistent."""


@dataclass(frozen=True)
class TranslationPair:
    publication: str
    language: str
    canonical: PurePosixPath
    translation: PurePosixPath


@dataclass(frozen=True)
class PageMetadata:
    language: str | None
    canonical_links: tuple[str, ...]
    alternates: tuple[tuple[str, str], ...]
    switcher_count: int
    switcher_links: tuple[tuple[str | None, str | None], ...]


class ReaderPageParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_languages: list[str | None] = []
        self.canonical_links: list[str] = []
        self.alternates: list[tuple[str, str]] = []
        self.switcher_count = 0
        self.switcher_links: list[tuple[str | None, str | None]] = []
        self._switcher_depth = 0

    @staticmethod
    def _attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for name, value in attrs:
            result.setdefault(name.casefold(), value)
        return result

    @staticmethod
    def _tokens(value: str | None) -> set[str]:
        return set(value.casefold().split()) if isinstance(value, str) else set()

    def _record_link(self, values: dict[str, str | None]) -> None:
        rel = self._tokens(values.get("rel"))
        href = values.get("href")
        if "canonical" in rel and isinstance(href, str):
            self.canonical_links.append(href)
        if "alternate" in rel:
            hreflang = values.get("hreflang")
            if isinstance(href, str) and isinstance(hreflang, str):
                self.alternates.append((hreflang, href))

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = self._attributes(attrs)
        lowered = tag.casefold()
        if lowered == "html":
            self.html_languages.append(values.get("lang"))
        if lowered == "link":
            self._record_link(values)

        starts_switcher = (
            lowered == "div"
            and "translation-switcher" in self._tokens(values.get("class"))
        )
        active_before = self._switcher_depth > 0
        if starts_switcher:
            self.switcher_count += 1
            if active_before:
                raise TranslationPairValidationError(
                    "translation switcher must not be nested"
                )
            self._switcher_depth = 1
        elif active_before:
            self._switcher_depth += 1

        if lowered == "a" and self._switcher_depth > 0:
            self.switcher_links.append((values.get("hreflang"), values.get("href")))

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = self._attributes(attrs)
        lowered = tag.casefold()
        if lowered == "html":
            self.html_languages.append(values.get("lang"))
        if lowered == "link":
            self._record_link(values)
        if lowered == "a" and self._switcher_depth > 0:
            self.switcher_links.append((values.get("hreflang"), values.get("href")))

    def handle_endtag(self, tag: str) -> None:
        if self._switcher_depth > 0:
            self._switcher_depth -= 1

    def metadata(self) -> PageMetadata:
        language = self.html_languages[0] if len(self.html_languages) == 1 else None
        return PageMetadata(
            language=language,
            canonical_links=tuple(self.canonical_links),
            alternates=tuple(self.alternates),
            switcher_count=self.switcher_count,
            switcher_links=tuple(self.switcher_links),
        )


def read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationPairValidationError(
            f"unable to read translation map {path}: {exc}"
        ) from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TranslationPairValidationError(
                    f"translation map contains duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise TranslationPairValidationError(
            f"unable to parse translation map {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise TranslationPairValidationError("translation map must be an object")
    return value


def safe_markdown_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise TranslationPairValidationError(
            f"{field} must be a safe relative Markdown path"
        )
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise TranslationPairValidationError(
            f"{field} must be a safe relative Markdown path"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.casefold() != ".md":
        raise TranslationPairValidationError(
            f"{field} must be a safe relative Markdown path"
        )
    return path


def load_pairs(path: Path) -> tuple[str, list[TranslationPair]]:
    data = read_json(path)
    expected = {"schema_version", "canonical_language", "translations"}
    if set(data) != expected:
        missing = sorted(expected - set(data))
        extra = sorted(set(data) - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unsupported " + ", ".join(extra))
        raise TranslationPairValidationError(
            "translation map fields are invalid: " + "; ".join(details)
        )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise TranslationPairValidationError(
            "translation map schema_version must be integer 1"
        )
    canonical_language = data["canonical_language"]
    if (
        not isinstance(canonical_language, str)
        or not LANGUAGE_TAG.fullmatch(canonical_language)
    ):
        raise TranslationPairValidationError(
            "translation map canonical_language must be a lowercase language tag"
        )
    entries = data["translations"]
    if not isinstance(entries, list):
        raise TranslationPairValidationError(
            "translation map translations must be an array"
        )

    pairs: list[TranslationPair] = []
    seen_pairs: set[tuple[PurePosixPath, str]] = set()
    seen_translations: set[PurePosixPath] = set()
    owners: dict[PurePosixPath, str] = {}
    for index, entry in enumerate(entries):
        field = f"translations[{index}]"
        if not isinstance(entry, dict) or set(entry) != {
            "publication",
            "language",
            "canonical_destination",
            "translation_destination",
        }:
            raise TranslationPairValidationError(
                f"{field} must contain publication, language, "
                "canonical_destination, and translation_destination"
            )
        publication = entry["publication"]
        language = entry["language"]
        if (
            not isinstance(publication, str)
            or not PUBLICATION_NAME.fullmatch(publication)
        ):
            raise TranslationPairValidationError(
                f"{field}.publication must be lowercase kebab-case"
            )
        if (
            not isinstance(language, str)
            or not LANGUAGE_TAG.fullmatch(language)
            or language == canonical_language
        ):
            raise TranslationPairValidationError(
                f"{field}.language must be a non-canonical lowercase language tag"
            )
        canonical = safe_markdown_path(
            entry["canonical_destination"],
            f"{field}.canonical_destination",
        )
        translation = safe_markdown_path(
            entry["translation_destination"],
            f"{field}.translation_destination",
        )
        expected_translation = PurePosixPath(language) / canonical
        if translation != expected_translation:
            raise TranslationPairValidationError(
                f"{field}.translation_destination must be {expected_translation}"
            )
        previous_owner = owners.setdefault(canonical, publication)
        if previous_owner != publication:
            raise TranslationPairValidationError(
                f"{field}.canonical_destination is assigned to multiple publications"
            )
        pair_key = (canonical, language)
        if pair_key in seen_pairs or translation in seen_translations:
            raise TranslationPairValidationError(
                f"{field} duplicates a translation mapping"
            )
        seen_pairs.add(pair_key)
        seen_translations.add(translation)
        pairs.append(
            TranslationPair(
                publication=publication,
                language=language,
                canonical=canonical,
                translation=translation,
            )
        )
    return canonical_language, pairs


def validate_canonical_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or parts.query
        or parts.fragment
    ):
        raise TranslationPairValidationError(
            "canonical URL must be an absolute HTTP or HTTPS URL without query or fragment"
        )
    path = parts.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def markdown_to_html_path(destination: PurePosixPath) -> PurePosixPath:
    if destination.name == "index.md":
        return destination.with_name("index.html")
    return destination.with_suffix("") / "index.html"


def public_url(destination: PurePosixPath, canonical_base: str) -> str:
    html_path = markdown_to_html_path(destination)
    if html_path.name == "index.html":
        route = html_path.parent.as_posix()
        if route == ".":
            route = ""
        elif route:
            route += "/"
    else:
        route = html_path.as_posix()
    return urljoin(canonical_base, route)


def parse_page(path: Path, *, require_language: bool) -> PageMetadata:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationPairValidationError(
            f"unable to read generated HTML {path}: {exc}"
        ) from exc
    parser = ReaderPageParser()
    try:
        parser.feed(source)
        parser.close()
    except TranslationPairValidationError as exc:
        raise TranslationPairValidationError(
            f"unable to parse generated HTML {path}: {exc}"
        ) from exc
    if require_language and len(parser.html_languages) != 1:
        raise TranslationPairValidationError(
            f"{path}: expected exactly one html language, "
            f"found {len(parser.html_languages)}"
        )
    return parser.metadata()


def exact_language_map(
    values: tuple[tuple[str, str], ...],
    field: str,
    path: Path,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for language, href in values:
        if language in result:
            raise TranslationPairValidationError(
                f"{path}: duplicate {field} language {language}"
            )
        result[language] = href
    return result


def switcher_language_map(
    values: tuple[tuple[str | None, str | None], ...],
    path: Path,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for language, href in values:
        if not isinstance(language, str) or not isinstance(href, str):
            raise TranslationPairValidationError(
                f"{path}: translation switcher links require href and hreflang"
            )
        if language in result:
            raise TranslationPairValidationError(
                f"{path}: duplicate translation switcher language {language}"
            )
        result[language] = href
    return result


def validate_page(
    *,
    path: Path,
    metadata: PageMetadata,
    language: str,
    canonical_url: str,
    alternates: dict[str, str],
    switcher_links: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    if metadata.language != language:
        errors.append(
            f"{path}: html lang is {metadata.language!r}, expected {language!r}"
        )
    if metadata.canonical_links != (canonical_url,):
        errors.append(
            f"{path}: canonical links are {metadata.canonical_links!r}, "
            f"expected {(canonical_url,)!r}"
        )
    if metadata.switcher_count != 1:
        errors.append(
            f"{path}: expected exactly one translation switcher, "
            f"found {metadata.switcher_count}"
        )
    try:
        actual_alternates = exact_language_map(
            metadata.alternates,
            "alternate",
            path,
        )
    except TranslationPairValidationError as exc:
        errors.append(str(exc))
    else:
        if actual_alternates != alternates:
            errors.append(
                f"{path}: alternates are {actual_alternates!r}, "
                f"expected {alternates!r}"
            )
    try:
        actual_switcher = switcher_language_map(metadata.switcher_links, path)
    except TranslationPairValidationError as exc:
        errors.append(str(exc))
    else:
        if actual_switcher != switcher_links:
            errors.append(
                f"{path}: translation switcher links are {actual_switcher!r}, "
                f"expected {switcher_links!r}"
            )
    return errors


def validate(
    site_root: Path,
    translation_map: Path,
    canonical_url: str,
) -> tuple[int, int]:
    try:
        site_root = site_root.resolve(strict=True)
    except OSError as exc:
        raise TranslationPairValidationError(
            f"unable to resolve generated site root {site_root}: {exc}"
        ) from exc
    canonical_base = validate_canonical_url(canonical_url)
    canonical_language, pairs = load_pairs(translation_map)

    groups: dict[PurePosixPath, list[TranslationPair]] = {}
    for pair in pairs:
        groups.setdefault(pair.canonical, []).append(pair)

    expected_pages: set[Path] = set()
    page_cache: dict[Path, PageMetadata] = {}
    errors: list[str] = []

    def metadata_for(destination: PurePosixPath) -> tuple[Path, PageMetadata | None]:
        html_relative = markdown_to_html_path(destination)
        page = site_root.joinpath(*html_relative.parts)
        expected_pages.add(page)
        if page in page_cache:
            return page, page_cache[page]
        if page.is_symlink() or not page.is_file():
            errors.append(
                f"{page}: expected generated translation-pair page is missing "
                "or not a regular file"
            )
            return page, None
        try:
            resolved = page.resolve(strict=True)
            resolved.relative_to(site_root)
        except (OSError, ValueError):
            errors.append(f"{page}: generated translation-pair page escapes site root")
            return page, None
        try:
            page_cache[page] = parse_page(page, require_language=True)
        except TranslationPairValidationError as exc:
            errors.append(str(exc))
            return page, None
        return page, page_cache[page]

    for canonical, group in sorted(
        groups.items(),
        key=lambda item: item[0].as_posix(),
    ):
        canonical_target = public_url(canonical, canonical_base)
        localized = {
            pair.language: public_url(pair.translation, canonical_base)
            for pair in sorted(group, key=lambda item: item.language)
        }
        alternates = {canonical_language: canonical_target, **localized}

        canonical_path, canonical_metadata = metadata_for(canonical)
        if canonical_metadata is not None:
            errors.extend(
                validate_page(
                    path=canonical_path,
                    metadata=canonical_metadata,
                    language=canonical_language,
                    canonical_url=canonical_target,
                    alternates=alternates,
                    switcher_links=localized,
                )
            )

        for pair in sorted(group, key=lambda item: item.language):
            translated_path, translated_metadata = metadata_for(pair.translation)
            if translated_metadata is None:
                continue
            errors.extend(
                validate_page(
                    path=translated_path,
                    metadata=translated_metadata,
                    language=pair.language,
                    canonical_url=canonical_target,
                    alternates=alternates,
                    switcher_links={canonical_language: canonical_target},
                )
            )

    for page in sorted(site_root.rglob("*.html")):
        if page in expected_pages or not page.is_file() or page.is_symlink():
            continue
        try:
            metadata = parse_page(page, require_language=False)
        except TranslationPairValidationError as exc:
            errors.append(str(exc))
            continue
        if metadata.switcher_count:
            errors.append(
                f"{page}: translation switcher exists without a current "
                "translation-publication mapping"
            )

    if errors:
        raise TranslationPairValidationError(
            "generated translation-pair validation failed:\n- "
            + "\n- ".join(errors)
        )
    return len(groups), len(pairs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--translation-map", required=True, type=Path)
    parser.add_argument("--canonical-url", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        group_count, pair_count = validate(
            args.site_root,
            args.translation_map,
            args.canonical_url,
        )
    except (OSError, TranslationPairValidationError) as exc:
        print(f"validate_translation_pairs.py: {exc}", file=sys.stderr)
        return 1
    print(f"translation groups validated: {group_count}")
    print(f"translation pairs validated: {pair_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
