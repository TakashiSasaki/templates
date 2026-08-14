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


class TranslationError(RuntimeError):
    """Raised when translation metadata or files violate the repository contract."""


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
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


def catalog_sources(root: Path) -> set[PurePosixPath]:
    catalog = read_json(
        root / "docs" / "publication-catalog.json",
        "publication catalog",
    )
    documents = catalog.get("documents")
    if not isinstance(documents, list):
        raise TranslationError("publication catalog documents must be an array")

    result: set[PurePosixPath] = set()
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise TranslationError(
                f"publication catalog documents[{index}] must be an object"
            )
        source = safe_path(
            document.get("source"),
            f"publication catalog documents[{index}].source",
        )
        result.add(source)
    return result


def validate_japanese_notice(path: Path, translation: PurePosixPath) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise TranslationError(
            f"unable to inspect Japanese translation notice: {translation}"
        ) from exc

    index = 0
    if lines and lines[0] == "---":
        try:
            index = lines.index("---", 1) + 1
        except ValueError as exc:
            raise TranslationError(
                f"Japanese translation has unterminated front matter: {translation}"
            ) from exc

    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith("# "):
        raise TranslationError(
            "Japanese translation must place a top-level title before the "
            f"non-authoritative notice: {translation}"
        )

    index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith(JA_NOTICE):
        raise TranslationError(
            "Japanese translation must place the non-authoritative notice "
            f"immediately after its top-level title: {translation}"
        )


def validate(root: Path) -> list[str]:
    root = root.resolve(strict=True)
    manifest = read_json(
        root / "translations" / "manifest.json",
        "translation manifest",
    )
    expected_manifest_keys = {
        "schema_version",
        "canonical_language",
        "translations",
    }
    if set(manifest) != expected_manifest_keys:
        raise TranslationError(
            "translation manifest must contain only schema_version, "
            "canonical_language, and translations"
        )

    schema_version = manifest["schema_version"]
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise TranslationError("translation manifest schema_version must be integer 1")
    if schema_version != 1:
        raise TranslationError("translation manifest schema_version must be integer 1")
    if manifest["canonical_language"] != "en":
        raise TranslationError("translation manifest canonical_language must be en")

    entries = manifest["translations"]
    if not isinstance(entries, list):
        raise TranslationError("translation manifest translations must be an array")

    published = catalog_sources(root)
    seen_pairs: set[tuple[PurePosixPath, str]] = set()
    declared_translation_paths: set[PurePosixPath] = set()

    for index, entry in enumerate(entries):
        field = f"translations[{index}]"
        required = {
            "canonical",
            "language",
            "translation",
            "canonical_blob_sha",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise TranslationError(
                f"{field} must contain canonical, language, translation, "
                "and canonical_blob_sha"
            )

        canonical = safe_path(entry["canonical"], f"{field}.canonical")
        language = entry["language"]
        translation = safe_path(entry["translation"], f"{field}.translation")
        blob_sha = entry["canonical_blob_sha"]

        if (
            not isinstance(language, str)
            or not LANGUAGE.fullmatch(language)
            or language == "en"
        ):
            raise TranslationError(
                f"{field}.language must be a non-English lowercase language tag"
            )
        if not isinstance(blob_sha, str) or not BLOB_SHA.fullmatch(blob_sha):
            raise TranslationError(
                f"{field}.canonical_blob_sha must be a full lowercase Git blob SHA"
            )
        if canonical.suffix.lower() != ".md" or translation.suffix.lower() != ".md":
            raise TranslationError(
                f"{field} canonical and translation paths must be Markdown"
            )
        if canonical not in published:
            raise TranslationError(
                f"{field}.canonical is not a published canonical document: {canonical}"
            )

        expected_translation = PurePosixPath("translations") / language / canonical
        if translation != expected_translation:
            raise TranslationError(
                f"{field}.translation must mirror the canonical path at "
                f"{expected_translation}"
            )

        pair = (canonical, language)
        if pair in seen_pairs:
            raise TranslationError(
                f"duplicate canonical/language translation pair: {canonical} {language}"
            )
        if translation in declared_translation_paths:
            raise TranslationError(f"duplicate translation path: {translation}")
        seen_pairs.add(pair)
        declared_translation_paths.add(translation)

        canonical_file = regular_file(root, canonical, f"{field}.canonical")
        translation_file = regular_file(root, translation, f"{field}.translation")
        actual_blob_sha = git_blob_sha(canonical_file)
        if actual_blob_sha != blob_sha:
            raise TranslationError(
                f"stale translation for {canonical}: expected canonical blob "
                f"{blob_sha}, current blob {actual_blob_sha}"
            )

        if language == "ja":
            validate_japanese_notice(translation_file, translation)

    discovered = {
        PurePosixPath(path.relative_to(root).as_posix())
        for path in (root / "translations").glob("*/**/*.md")
        if path.is_file()
    }
    undeclared = sorted(discovered - declared_translation_paths)
    missing = sorted(declared_translation_paths - discovered)
    if undeclared:
        paths = ", ".join(str(path) for path in undeclared)
        raise TranslationError(f"undeclared translation Markdown: {paths}")
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise TranslationError(f"declared translation Markdown not discovered: {paths}")

    return [
        f"canonical language: {manifest['canonical_language']}",
        f"translations validated: {len(entries)}",
    ]


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    try:
        print("\n".join(validate(root)))
    except (TranslationError, OSError) as exc:
        print(f"validate_translations.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
