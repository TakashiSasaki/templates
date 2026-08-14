#!/usr/bin/env python3
"""Validate non-authoritative translations against canonical English sources."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

LANGUAGE = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")
BLOB_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
JA_NOTICE = "> **参考訳（非正本）:**"
ALLOWED_SURFACES = {"reader", "guided"}


class TranslationError(RuntimeError):
    pass


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TranslationError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TranslationError(f"{label} contains duplicate member: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise TranslationError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TranslationError(f"{label} must be an object")
    return value


def safe_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise TranslationError(f"{field} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise TranslationError(f"{field} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise TranslationError(f"{field} must be a safe relative POSIX path")
    return path


def regular_file(root: Path, relative: PurePosixPath, field: str) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise TranslationError(f"{field} must not traverse a symlink: {relative}")
    if not current.is_file():
        raise TranslationError(f"{field} must be an existing regular file: {relative}")
    return current


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()  # noqa: S324


def catalog_sources(root: Path) -> set[PurePosixPath]:
    catalog = read_json(root / "docs" / "publication-catalog.json", "publication catalog")
    documents = catalog.get("documents")
    if not isinstance(documents, list):
        raise TranslationError("publication catalog documents must be an array")
    result: set[PurePosixPath] = set()
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise TranslationError(f"publication catalog documents[{index}] must be an object")
        result.add(safe_path(document.get("source"), f"publication catalog documents[{index}].source"))
    return result


def validate_japanese_notice(path: Path, translation: PurePosixPath) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    if lines and lines[0] == "---":
        try:
            index = lines.index("---", 1) + 1
        except ValueError as exc:
            raise TranslationError(f"Japanese translation has unterminated front matter: {translation}") from exc
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith("# "):
        raise TranslationError(f"Japanese translation must place a top-level title before the non-authoritative notice: {translation}")
    index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith(JA_NOTICE):
        raise TranslationError(f"Japanese translation must place the non-authoritative notice immediately after its top-level title: {translation}")


def validate_surfaces(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TranslationError(f"{field} must be a non-empty array")
    surfaces: list[str] = []
    for index, surface in enumerate(value):
        if not isinstance(surface, str) or surface not in ALLOWED_SURFACES:
            raise TranslationError(f"{field}[{index}] must be one of reader or guided")
        if surface in surfaces:
            raise TranslationError(f"{field} must not contain duplicate surfaces")
        surfaces.append(surface)
    return tuple(surfaces)


def validate(root: Path) -> list[str]:
    root = root.resolve(strict=True)
    manifest = read_json(root / "translations" / "manifest.json", "translation manifest")
    if set(manifest) != {"schema_version", "canonical_language", "translations"}:
        raise TranslationError("translation manifest must contain only schema_version, canonical_language, and translations")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 2:
        raise TranslationError("translation manifest schema_version must be integer 2")
    if manifest["canonical_language"] != "en":
        raise TranslationError("translation manifest canonical_language must be en")
    entries = manifest["translations"]
    if not isinstance(entries, list):
        raise TranslationError("translation manifest translations must be an array")

    published = catalog_sources(root)
    seen_pairs: set[tuple[PurePosixPath, str]] = set()
    declared_paths: set[PurePosixPath] = set()
    counts = {"reader": 0, "guided": 0}
    required = {"canonical", "language", "translation", "canonical_blob_sha", "surfaces"}

    for index, entry in enumerate(entries):
        field = f"translations[{index}]"
        if not isinstance(entry, dict) or set(entry) != required:
            raise TranslationError(f"{field} must contain canonical, language, translation, canonical_blob_sha, and surfaces")
        canonical = safe_path(entry["canonical"], f"{field}.canonical")
        translation = safe_path(entry["translation"], f"{field}.translation")
        language = entry["language"]
        blob_sha = entry["canonical_blob_sha"]
        surfaces = validate_surfaces(entry["surfaces"], f"{field}.surfaces")
        if not isinstance(language, str) or not LANGUAGE.fullmatch(language) or language == "en":
            raise TranslationError(f"{field}.language must be a non-English lowercase language tag")
        if not isinstance(blob_sha, str) or not BLOB_SHA.fullmatch(blob_sha):
            raise TranslationError(f"{field}.canonical_blob_sha must be a full lowercase Git blob SHA")
        if canonical.suffix.lower() != ".md" or translation.suffix.lower() != ".md":
            raise TranslationError(f"{field} canonical and translation paths must be Markdown")
        if "reader" in surfaces and canonical not in published:
            raise TranslationError(f"{field}.canonical is not a published canonical document: {canonical}")
        if "guided" in surfaces and canonical.name != "index.md":
            raise TranslationError(f"{field}.canonical must be an index.md document for guided use: {canonical}")
        expected = PurePosixPath("translations") / language / canonical
        if translation != expected:
            raise TranslationError(f"{field}.translation must mirror the canonical path at {expected}")
        pair = (canonical, language)
        if pair in seen_pairs:
            raise TranslationError(f"duplicate canonical/language translation pair: {canonical} {language}")
        if translation in declared_paths:
            raise TranslationError(f"duplicate translation path: {translation}")
        seen_pairs.add(pair)
        declared_paths.add(translation)
        canonical_file = regular_file(root, canonical, f"{field}.canonical")
        translation_file = regular_file(root, translation, f"{field}.translation")
        actual = git_blob_sha(canonical_file)
        if actual != blob_sha:
            raise TranslationError(f"stale translation for {canonical}: expected canonical blob {blob_sha}, current blob {actual}")
        if language == "ja":
            validate_japanese_notice(translation_file, translation)
        for surface in surfaces:
            counts[surface] += 1

    readme = PurePosixPath("translations/README.md")
    discovered = {
        PurePosixPath(path.relative_to(root).as_posix())
        for path in (root / "translations").rglob("*.md")
        if path.is_file() and PurePosixPath(path.relative_to(root).as_posix()) != readme
    }
    undeclared = sorted(discovered - declared_paths)
    missing = sorted(declared_paths - discovered)
    if undeclared:
        raise TranslationError("undeclared translation Markdown: " + ", ".join(map(str, undeclared)))
    if missing:
        raise TranslationError("declared translation Markdown not discovered: " + ", ".join(map(str, missing)))
    return [
        f"canonical language: {manifest['canonical_language']}",
        f"translations validated: {len(entries)}",
        f"reader translations: {counts['reader']}",
        f"guided translations: {counts['guided']}",
    ]


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    try:
        print("\n".join(validate(root)))
    except (TranslationError, OSError, UnicodeError) as exc:
        print(f"validate_translations.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
