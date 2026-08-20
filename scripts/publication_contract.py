#!/usr/bin/env python3
"""Site-owned schema-v3 publication protocol parser and validator.

This module is deliberately stdlib-only. Site imports it during assembly, and
provider CI may execute this exact file from a reviewed full Site revision.
Provider-specific publication semantics remain outside this module.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

CATALOG_RELATIVE_PATH = PurePosixPath("docs/publication-catalog.json")
NAME_PATTERN = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class PublicationContractError(RuntimeError):
    """Raised when the shared publication protocol is violated."""


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


@dataclass(frozen=True)
class PublicationCatalog:
    documents: tuple[Document, ...]
    assets: tuple[Asset, ...]
    glossary_source: PurePosixPath | None

    @property
    def documents_by_id(self) -> dict[str, Document]:
        return {document.document_id: document for document in self.documents}


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PublicationContractError(f"unable to read {label} {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicationContractError(f"{label} must be valid UTF-8: {path}") from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PublicationContractError(
                    f"{label} contains duplicate object member: {key}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise PublicationContractError(
            f"{label} contains non-standard numeric constant: {value}"
        )

    try:
        value = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise PublicationContractError(
            f"unable to parse {label} {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise PublicationContractError(f"{label} must be a JSON object")
    return value


def safe_relative_path(value: Any, field: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
        raise PublicationContractError(
            f"{field} must be a safe non-empty relative POSIX path"
        )
    parts = value.split("/")
    if any(
        part in ("", ".", "..") or part.casefold() == ".git"
        for part in parts
    ):
        raise PublicationContractError(
            f"{field} must be a safe non-empty relative POSIX path"
        )
    path = PurePosixPath(value)
    if path.is_absolute():
        raise PublicationContractError(
            f"{field} must be a safe non-empty relative POSIX path"
        )
    return path


def parse_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not NAME_PATTERN.fullmatch(value):
        raise PublicationContractError(f"{field} must be lowercase kebab-case")
    return value


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
            raise PublicationContractError(
                f"{field} must remain within source root: {relative}"
            ) from exc
        if current.is_symlink():
            raise PublicationContractError(
                f"{field} must not traverse a symbolic link: {relative}"
            )
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
                raise PublicationContractError(
                    f"{description} must not overlap: {first} and {second}"
                )


def _parse_document(raw: Any, index: int, label: str) -> Document:
    field = f"{label}.documents[{index}]"
    if not isinstance(raw, dict):
        raise PublicationContractError(f"{field} must be an object")
    expected = {"id", "source", "optional", "home"}
    unknown = set(raw) - expected
    missing = expected - set(raw)
    if unknown:
        raise PublicationContractError(
            f"{field} contains unsupported fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise PublicationContractError(
            f"{field} is missing required fields: {', '.join(sorted(missing))}"
        )

    document_id = parse_name(raw["id"], f"{field}.id")
    source = safe_relative_path(raw["source"], f"{field}.source")
    if source.suffix.lower() != ".md":
        raise PublicationContractError(f"{field}.source must be Markdown")
    optional = raw["optional"]
    home = raw["home"]
    if type(optional) is not bool:
        raise PublicationContractError(f"{field}.optional must be boolean")
    if type(home) is not bool:
        raise PublicationContractError(f"{field}.home must be boolean")
    return Document(document_id, source, optional, home)


def _parse_asset(raw: Any, index: int, label: str) -> Asset:
    field = f"{label}.assets[{index}]"
    if not isinstance(raw, dict):
        raise PublicationContractError(f"{field} must be an object")
    expected = {"source", "destination", "optional"}
    unknown = set(raw) - expected
    missing = expected - set(raw)
    if unknown:
        raise PublicationContractError(
            f"{field} contains unsupported fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise PublicationContractError(
            f"{field} is missing required fields: {', '.join(sorted(missing))}"
        )
    source = safe_relative_path(raw["source"], f"{field}.source")
    destination = safe_relative_path(raw["destination"], f"{field}.destination")
    optional = raw["optional"]
    if type(optional) is not bool:
        raise PublicationContractError(f"{field}.optional must be boolean")
    return Asset(source, destination, optional)


def _parse_glossary_source(raw: Any, label: str) -> PurePosixPath:
    field = f"{label}.glossary"
    if not isinstance(raw, dict) or set(raw) != {"source"}:
        raise PublicationContractError(
            f"{field} must contain exactly the source field"
        )
    source = safe_relative_path(raw["source"], f"{field}.source")
    if source.suffix.lower() != ".yml":
        raise PublicationContractError(f"{field}.source must be a .yml file")
    return source


def parse_publication_catalog(path: Path, *, label: str = "publication catalog") -> PublicationCatalog:
    data = read_json_object(path, label)
    schema_version = data.get("schema_version")
    if type(schema_version) is not int or schema_version != 3:
        raise PublicationContractError(f"{label} schema_version must be integer 3")

    allowed_top_level = {"schema_version", "documents", "assets", "glossary"}
    unknown = set(data) - allowed_top_level
    if unknown:
        raise PublicationContractError(
            f"{label} has unsupported fields: {', '.join(sorted(unknown))}"
        )

    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise PublicationContractError(
            f"{label} documents must be a non-empty array"
        )
    documents = tuple(
        _parse_document(raw, index, label)
        for index, raw in enumerate(raw_documents)
    )

    document_ids = [document.document_id for document in documents]
    if len(set(document_ids)) != len(document_ids):
        raise PublicationContractError(f"{label} document IDs must be unique")
    document_sources = [document.source for document in documents]
    if len(set(document_sources)) != len(document_sources):
        raise PublicationContractError(f"{label} document sources must be unique")
    homes = [document for document in documents if document.home]
    if len(homes) != 1:
        raise PublicationContractError(
            f"{label} must define exactly one home document"
        )
    if homes[0].optional:
        raise PublicationContractError(f"{label} home document must not be optional")

    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise PublicationContractError(f"{label} assets must be an array")
    assets = tuple(
        _parse_asset(raw, index, label)
        for index, raw in enumerate(raw_assets)
    )
    asset_sources = [asset.source for asset in assets]
    if len(set(asset_sources)) != len(asset_sources):
        raise PublicationContractError(f"{label} asset sources must be unique")
    reject_overlapping_paths(asset_sources, f"{label} asset sources")
    asset_destinations = [asset.destination for asset in assets]
    if len(set(asset_destinations)) != len(asset_destinations):
        raise PublicationContractError(f"{label} asset destinations must be unique")
    reject_overlapping_paths(asset_destinations, f"{label} asset destinations")

    glossary_source: PurePosixPath | None = None
    if "glossary" in data:
        glossary_source = _parse_glossary_source(data["glossary"], label)
        for asset_source in asset_sources:
            if paths_overlap(glossary_source, asset_source):
                raise PublicationContractError(
                    f"{label} glossary source must not overlap asset sources"
                )

    return PublicationCatalog(documents, assets, glossary_source)


def asset_files(
    source_root: Path,
    relative: PurePosixPath,
    field: str,
) -> tuple[Path, ...]:
    path = resolve_without_symlinks(source_root, relative, field)
    if path.is_file():
        if path.suffix.lower() == ".md":
            raise PublicationContractError(
                f"{field} must not publish Markdown as an asset"
            )
        return (path,)
    if not path.is_dir():
        raise PublicationContractError(f"{field} does not exist: {relative}")

    files: list[Path] = []
    pending = [path]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise PublicationContractError(
                f"unable to inspect {field} {directory}: {exc}"
            ) from exc
        for child in children:
            child_relative = child.relative_to(path)
            if any(part.casefold() == ".git" for part in child_relative.parts):
                raise PublicationContractError(
                    f"{field} contains a .git subtree: {child}"
                )
            if child.is_symlink():
                raise PublicationContractError(
                    f"{field} contains a symbolic link: {child}"
                )
            if child.is_dir():
                pending.append(child)
                continue
            if not child.is_file():
                raise PublicationContractError(
                    f"{field} contains an unsupported entry: {child}"
                )
            if child.suffix.lower() == ".md":
                raise PublicationContractError(
                    f"{field} contains Markdown outside the document catalog: {child}"
                )
            files.append(child)
    if not files:
        raise PublicationContractError(f"{field} must not be empty: {relative}")
    return tuple(files)


def validate_publication_sources(
    source_root: Path,
    catalog: PublicationCatalog,
    *,
    label: str = "publication catalog",
) -> None:
    source_root = source_root.resolve(strict=True)
    for index, document in enumerate(catalog.documents):
        field = f"{label}.documents[{index}].source"
        path = resolve_without_symlinks(source_root, document.source, field)
        if path.is_file():
            continue
        if document.optional and not path.exists():
            continue
        raise PublicationContractError(
            f"declared document source is not a regular file: {document.source}"
        )

    for index, asset in enumerate(catalog.assets):
        field = f"{label}.assets[{index}].source"
        path = resolve_without_symlinks(source_root, asset.source, field)
        if not path.exists():
            if asset.optional:
                continue
            raise PublicationContractError(
                f"declared asset source does not exist: {asset.source}"
            )
        files = asset_files(source_root, asset.source, field)
        if path.is_file() and asset.destination.suffix.lower() == ".md":
            raise PublicationContractError(
                f"{label}.assets[{index}].destination must not publish Markdown"
            )
        if not files:
            raise AssertionError("asset_files must return at least one file")

    if catalog.glossary_source is not None:
        path = resolve_without_symlinks(
            source_root,
            catalog.glossary_source,
            f"{label}.glossary.source",
        )
        if not path.is_file():
            raise PublicationContractError(
                "declared glossary source is not a regular file: "
                f"{catalog.glossary_source}"
            )


def load_publication_catalog(
    source_root: Path,
    *,
    catalog_relative: PurePosixPath = CATALOG_RELATIVE_PATH,
    label: str = "publication catalog",
    validate_sources: bool = True,
) -> PublicationCatalog:
    source_root = source_root.resolve(strict=True)
    catalog_path = resolve_without_symlinks(source_root, catalog_relative, label)
    if not catalog_path.is_file():
        raise PublicationContractError(
            f"{label} must identify an existing regular file: {catalog_relative}"
        )
    catalog = parse_publication_catalog(catalog_path, label=label)
    if validate_sources:
        validate_publication_sources(source_root, catalog, label=label)
    return catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument(
        "--catalog",
        default=CATALOG_RELATIVE_PATH.as_posix(),
        help="catalog path relative to --source-root",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog_relative = safe_relative_path(args.catalog, "--catalog")
        catalog = load_publication_catalog(
            args.source_root,
            catalog_relative=catalog_relative,
        )
    except (PublicationContractError, OSError) as exc:
        print(f"publication contract validation failed: {exc}", file=sys.stderr)
        return 1

    print(
        "validated schema-v3 publication contract: "
        f"{len(catalog.documents)} document(s), "
        f"{len(catalog.assets)} asset root(s), "
        f"glossary={'yes' if catalog.glossary_source is not None else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
