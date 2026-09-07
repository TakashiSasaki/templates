#!/usr/bin/env python3
"""Site-owned schema-v4 publication protocol with generated asset lifecycle.

Schema v4 keeps the existing document/glossary/path safety model and makes an
asset's source lifecycle explicit: ``tracked`` sources must exist in the checked
out tree, while ``generated`` sources may be absent only during the explicit
pre-materialization validation phase. Provider-specific generation semantics do
not move into Site.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.publication_contract import (  # noqa: E402
    CATALOG_RELATIVE_PATH,
    Document,
    PublicationContractError,
    asset_files,
    parse_name,
    paths_overlap,
    read_json_object,
    reject_overlapping_paths,
    resolve_without_symlinks,
    safe_relative_path,
)

SCHEMA_VERSION = 4
SOURCE_KINDS = frozenset({"tracked", "generated"})


@dataclass(frozen=True)
class AssetV4:
    source: PurePosixPath
    destination: PurePosixPath
    optional: bool
    source_kind: str


@dataclass(frozen=True)
class PublicationCatalogV4:
    documents: tuple[Document, ...]
    assets: tuple[AssetV4, ...]
    glossary_source: PurePosixPath | None

    @property
    def documents_by_id(self) -> dict[str, Document]:
        return {document.document_id: document for document in self.documents}

    @property
    def generated_assets(self) -> tuple[AssetV4, ...]:
        return tuple(asset for asset in self.assets if asset.source_kind == "generated")


def _parse_document(raw: Any, index: int, label: str) -> Document:
    field = f"{label}.documents[{index}]"
    expected = {"id", "source", "optional", "home"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise PublicationContractError(
            f"{field} must contain exactly id, source, optional, and home"
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


def _parse_asset(raw: Any, index: int, label: str) -> AssetV4:
    field = f"{label}.assets[{index}]"
    expected = {"source", "destination", "optional", "source_kind"}
    if not isinstance(raw, dict):
        raise PublicationContractError(f"{field} must be an object")
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
    source_kind = raw["source_kind"]
    if source_kind not in SOURCE_KINDS:
        raise PublicationContractError(
            f"{field}.source_kind must be tracked or generated"
        )
    return AssetV4(source, destination, optional, source_kind)


def parse_publication_catalog_v4(
    path: Path,
    *,
    label: str = "publication catalog",
) -> PublicationCatalogV4:
    data = read_json_object(path, label)
    if type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise PublicationContractError(f"{label} schema_version must be integer 4")
    allowed = {"schema_version", "documents", "assets", "glossary"}
    unknown = set(data) - allowed
    if unknown:
        raise PublicationContractError(
            f"{label} has unsupported fields: {', '.join(sorted(unknown))}"
        )
    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise PublicationContractError(f"{label} documents must be a non-empty array")
    documents = tuple(_parse_document(raw, index, label) for index, raw in enumerate(raw_documents))
    ids = [document.document_id for document in documents]
    sources = [document.source for document in documents]
    if len(set(ids)) != len(ids):
        raise PublicationContractError(f"{label} document IDs must be unique")
    if len(set(sources)) != len(sources):
        raise PublicationContractError(f"{label} document sources must be unique")
    homes = [document for document in documents if document.home]
    if len(homes) != 1 or homes[0].optional:
        raise PublicationContractError(f"{label} must define exactly one non-optional home document")

    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise PublicationContractError(f"{label} assets must be an array")
    assets = tuple(_parse_asset(raw, index, label) for index, raw in enumerate(raw_assets))
    asset_sources = [asset.source for asset in assets]
    asset_destinations = [asset.destination for asset in assets]
    if len(set(asset_sources)) != len(asset_sources):
        raise PublicationContractError(f"{label} asset sources must be unique")
    if len(set(asset_destinations)) != len(asset_destinations):
        raise PublicationContractError(f"{label} asset destinations must be unique")
    reject_overlapping_paths(asset_sources, f"{label} asset sources")
    reject_overlapping_paths(asset_destinations, f"{label} asset destinations")

    glossary_source: PurePosixPath | None = None
    if "glossary" in data:
        raw_glossary = data["glossary"]
        if not isinstance(raw_glossary, dict) or set(raw_glossary) != {"source"}:
            raise PublicationContractError(f"{label}.glossary must contain exactly source")
        glossary_source = safe_relative_path(raw_glossary["source"], f"{label}.glossary.source")
        if glossary_source.suffix.lower() != ".yml":
            raise PublicationContractError(f"{label}.glossary.source must be a .yml file")
        for asset_source in asset_sources:
            if paths_overlap(glossary_source, asset_source):
                raise PublicationContractError(f"{label} glossary source must not overlap asset sources")

    return PublicationCatalogV4(documents, assets, glossary_source)


def validate_publication_sources_v4(
    source_root: Path,
    catalog: PublicationCatalogV4,
    *,
    label: str = "publication catalog",
    phase: str = "materialized",
) -> None:
    if phase not in {"source", "materialized"}:
        raise PublicationContractError("publication validation phase must be source or materialized")
    source_root = source_root.resolve(strict=True)
    for index, document in enumerate(catalog.documents):
        field = f"{label}.documents[{index}].source"
        path = resolve_without_symlinks(source_root, document.source, field)
        if path.is_file():
            continue
        if document.optional and not path.exists():
            continue
        raise PublicationContractError(f"declared document source is not a regular file: {document.source}")

    for index, asset in enumerate(catalog.assets):
        field = f"{label}.assets[{index}].source"
        path = resolve_without_symlinks(source_root, asset.source, field)
        if not path.exists():
            if asset.optional:
                continue
            if asset.source_kind == "generated" and phase == "source":
                continue
            raise PublicationContractError(f"declared asset source does not exist: {asset.source}")
        files = asset_files(source_root, asset.source, field)
        if path.is_file() and asset.destination.suffix.lower() == ".md":
            raise PublicationContractError(f"{label}.assets[{index}].destination must not publish Markdown")
        if not files:
            raise AssertionError("asset_files must return at least one file")

    if catalog.glossary_source is not None:
        path = resolve_without_symlinks(source_root, catalog.glossary_source, f"{label}.glossary.source")
        if not path.is_file():
            raise PublicationContractError(f"declared glossary source is not a regular file: {catalog.glossary_source}")


def load_publication_catalog_v4(
    source_root: Path,
    *,
    catalog_relative: PurePosixPath = CATALOG_RELATIVE_PATH,
    label: str = "publication catalog",
    phase: str = "materialized",
) -> PublicationCatalogV4:
    source_root = source_root.resolve(strict=True)
    catalog_path = resolve_without_symlinks(source_root, catalog_relative, label)
    if not catalog_path.is_file():
        raise PublicationContractError(f"{label} must identify an existing regular file: {catalog_relative}")
    catalog = parse_publication_catalog_v4(catalog_path, label=label)
    validate_publication_sources_v4(source_root, catalog, label=label, phase=phase)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--catalog", default=CATALOG_RELATIVE_PATH.as_posix())
    parser.add_argument("--phase", choices=("source", "materialized"), default="materialized")
    args = parser.parse_args()
    try:
        catalog = load_publication_catalog_v4(
            args.source_root,
            catalog_relative=safe_relative_path(args.catalog, "--catalog"),
            phase=args.phase,
        )
    except (PublicationContractError, OSError) as exc:
        print(f"publication contract validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        "validated schema-v4 publication contract: "
        f"{len(catalog.documents)} document(s), {len(catalog.assets)} asset root(s), "
        f"generated={len(catalog.generated_assets)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
