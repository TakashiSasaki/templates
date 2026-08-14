#!/usr/bin/env python3
"""Validate a branch-owned documentation publication catalog."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

DOCUMENT_ID_PATTERN = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class CatalogError(RuntimeError):
    """Raised when a publication catalog or declared source is invalid."""


@dataclass(frozen=True)
class Document:
    document_id: str
    source: PurePosixPath
    optional: bool
    home: bool


@dataclass(frozen=True)
class Asset:
    source: PurePosixPath
    destination: PurePosixPath
    optional: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("docs/publication-catalog.json"),
    )
    parser.add_argument("--source-root", type=Path, default=Path("."))
    return parser.parse_args()


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CatalogError(f"unable to read catalog {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CatalogError(f"catalog must be valid UTF-8: {path}") from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CatalogError(f"catalog contains duplicate object member: {key}")
            result[key] = value
        return result

    try:
        data = json.loads(text, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise CatalogError(f"unable to parse catalog {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError("catalog must be a JSON object")
    return data


def safe_relative_path(value: Any, field: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
        raise CatalogError(f"{field} must be a safe non-empty relative POSIX path")
    parts = value.split("/")
    if any(
        part in ("", ".", "..") or part.casefold() == ".git"
        for part in parts
    ):
        raise CatalogError(f"{field} must be a safe non-empty relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise CatalogError(f"{field} must be a safe non-empty relative POSIX path")
    return path


def parse_document(raw: Any, index: int) -> Document:
    field = f"documents[{index}]"
    if not isinstance(raw, dict):
        raise CatalogError(f"{field} must be an object")
    expected = {"id", "source", "optional", "home"}
    unknown = set(raw) - expected
    missing = expected - set(raw)
    if unknown:
        raise CatalogError(
            f"{field} contains unsupported fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise CatalogError(
            f"{field} is missing required fields: {', '.join(sorted(missing))}"
        )

    document_id = raw["id"]
    if (
        not isinstance(document_id, str)
        or not DOCUMENT_ID_PATTERN.fullmatch(document_id)
    ):
        raise CatalogError(f"{field}.id must be a lowercase kebab-case document ID")
    source = safe_relative_path(raw["source"], f"{field}.source")
    if source.suffix.lower() != ".md":
        raise CatalogError(f"{field}.source must be a Markdown file")
    optional = raw["optional"]
    home = raw["home"]
    if not isinstance(optional, bool):
        raise CatalogError(f"{field}.optional must be boolean")
    if not isinstance(home, bool):
        raise CatalogError(f"{field}.home must be boolean")
    return Document(document_id, source, optional, home)


def parse_asset(raw: Any, index: int) -> Asset:
    field = f"assets[{index}]"
    if not isinstance(raw, dict):
        raise CatalogError(f"{field} must be an object")
    expected = {"source", "destination", "optional"}
    unknown = set(raw) - expected
    missing = expected - set(raw)
    if unknown:
        raise CatalogError(
            f"{field} contains unsupported fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise CatalogError(
            f"{field} is missing required fields: {', '.join(sorted(missing))}"
        )
    source = safe_relative_path(raw["source"], f"{field}.source")
    destination = safe_relative_path(raw["destination"], f"{field}.destination")
    optional = raw["optional"]
    if not isinstance(optional, bool):
        raise CatalogError(f"{field}.optional must be boolean")
    return Asset(source, destination, optional)


def resolve_without_symlinks(
    source_root: Path,
    relative: PurePosixPath,
    field: str,
) -> Path:
    source_root = source_root.resolve(strict=True)
    current = source_root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(source_root)
        except ValueError as exc:
            raise CatalogError(
                f"{field} must remain within source root: {relative}"
            ) from exc
        if current.is_symlink():
            raise CatalogError(f"{field} must not traverse a symbolic link: {relative}")
    return current


def paths_overlap(first: PurePosixPath, second: PurePosixPath) -> bool:
    return first == second or first in second.parents or second in first.parents


def reject_overlapping_paths(
    paths: list[PurePosixPath],
    description: str,
) -> None:
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            if paths_overlap(first, second):
                raise CatalogError(
                    f"{description} must not overlap: {first} and {second}"
                )


def validate_asset_tree(path: Path, field: str) -> None:
    if path.is_symlink():
        raise CatalogError(f"{field} must not be a symbolic link: {path}")
    if path.is_file():
        if path.suffix.lower() == ".md":
            raise CatalogError(f"{field} must not publish Markdown as an asset")
        return
    if not path.is_dir():
        raise CatalogError(f"{field} does not exist: {path}")
    for entry in path.rglob("*"):
        relative_entry = entry.relative_to(path)
        if any(part.casefold() == ".git" for part in relative_entry.parts):
            raise CatalogError(f"{field} contains a .git subtree: {entry}")
        if entry.is_symlink():
            raise CatalogError(f"{field} contains a symbolic link: {entry}")
        if entry.is_file() and entry.suffix.lower() == ".md":
            raise CatalogError(
                f"{field} contains Markdown outside the document catalog: {entry}"
            )


def validate_catalog(
    catalog_path: Path,
    source_root: Path,
) -> tuple[list[Document], list[Asset]]:
    data = read_json_object(catalog_path)
    schema_version = data.get("schema_version")
    if type(schema_version) is not int or schema_version not in (1, 2):
        raise CatalogError("schema_version must be the integer 1 or 2")
    if schema_version == 1 and "assets" in data:
        raise CatalogError("schema_version 1 does not support assets")

    allowed_top_level = {"schema_version", "documents"}
    if schema_version == 2:
        allowed_top_level.add("assets")
    unknown = set(data) - allowed_top_level
    if unknown:
        raise CatalogError(
            "catalog contains unsupported top-level fields: "
            + ", ".join(sorted(unknown))
        )

    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise CatalogError("documents must be a non-empty array")
    documents = [parse_document(raw, index) for index, raw in enumerate(raw_documents)]

    document_ids = [document.document_id for document in documents]
    if len(set(document_ids)) != len(document_ids):
        raise CatalogError("document IDs must be unique")
    document_sources = [document.source for document in documents]
    if len(set(document_sources)) != len(document_sources):
        raise CatalogError("document sources must be unique")
    homes = [document for document in documents if document.home]
    if len(homes) != 1:
        raise CatalogError("catalog must define exactly one home document")
    if homes[0].optional:
        raise CatalogError("catalog home document must not be optional")

    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise CatalogError("assets must be an array")
    assets = [parse_asset(raw, index) for index, raw in enumerate(raw_assets)]
    asset_sources = [asset.source for asset in assets]
    if len(set(asset_sources)) != len(asset_sources):
        raise CatalogError("asset sources must be unique")
    reject_overlapping_paths(asset_sources, "asset sources")
    asset_destinations = [asset.destination for asset in assets]
    if len(set(asset_destinations)) != len(asset_destinations):
        raise CatalogError("asset destinations must be unique")
    reject_overlapping_paths(asset_destinations, "asset destinations")

    source_root = source_root.resolve(strict=True)
    for index, document in enumerate(documents):
        path = resolve_without_symlinks(
            source_root, document.source, f"documents[{index}].source"
        )
        if path.is_file():
            continue
        if document.optional and not path.exists():
            continue
        raise CatalogError(
            "declared document source is not a regular file: "
            f"{document.source}"
        )

    for index, asset in enumerate(assets):
        path = resolve_without_symlinks(
            source_root, asset.source, f"assets[{index}].source"
        )
        if not path.exists():
            if asset.optional:
                continue
            raise CatalogError(
                f"declared asset source does not exist: {asset.source}"
            )
        validate_asset_tree(path, f"assets[{index}].source")

    return documents, assets


def main() -> int:
    args = parse_args()
    try:
        documents, assets = validate_catalog(args.catalog, args.source_root)
    except (CatalogError, OSError) as exc:
        print(f"publication catalog validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"validated {len(documents)} publication document(s) "
        f"and {len(assets)} asset root(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
