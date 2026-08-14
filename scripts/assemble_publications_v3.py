#!/usr/bin/env python3
"""Run the Site publication assembler with publication-catalog schema v3 support."""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_publications as legacy
from scripts.glossary import GlossaryError, glossary_source_from_catalog

AssemblyError = legacy.AssemblyError


def load_catalog(
    name: str,
    root: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Load catalog versions 1-3 while preserving legacy assembly semantics."""
    catalog_path = legacy.resolve(
        root,
        PurePosixPath("docs/publication-catalog.json"),
        f"{name} catalog",
    )
    data = legacy.read_json(catalog_path, f"{name} catalog")
    version = data.get("schema_version")
    if type(version) is not int or version not in (1, 2, 3):
        raise AssemblyError(
            f"{name} catalog schema_version must be integer 1, 2, or 3"
        )

    allowed = {"schema_version", "documents"}
    if version >= 2:
        allowed.add("assets")
    if version == 3:
        allowed.add("glossary")
    unknown = set(data) - allowed
    if unknown:
        raise AssemblyError(
            f"{name} catalog has unsupported fields: "
            + ", ".join(sorted(unknown))
        )

    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise AssemblyError(
            f"{name} catalog documents must be a non-empty array"
        )

    documents: dict[str, dict[str, Any]] = {}
    document_sources: set[PurePosixPath] = set()
    homes = 0
    for index, raw in enumerate(raw_documents):
        field = f"{name}.documents[{index}]"
        if (
            not isinstance(raw, dict)
            or set(raw) != {"id", "source", "optional", "home"}
        ):
            raise AssemblyError(
                f"{field} must contain id, source, optional, and home"
            )
        document_id = legacy.parse_name(raw["id"], f"{field}.id")
        source = legacy.safe_path(raw["source"], f"{field}.source")
        if source.suffix.lower() != ".md":
            raise AssemblyError(f"{field}.source must be Markdown")
        if not isinstance(raw["optional"], bool) or not isinstance(raw["home"], bool):
            raise AssemblyError(
                f"{field}.optional and home must be boolean"
            )
        if document_id in documents or source in document_sources:
            raise AssemblyError(
                f"{name} catalog document IDs and sources must be unique"
            )
        if raw["home"]:
            homes += 1
            if raw["optional"]:
                raise AssemblyError(
                    f"{name} catalog home must not be optional"
                )
        documents[document_id] = {
            "source": source,
            "optional": raw["optional"],
            "home": raw["home"],
        }
        document_sources.add(source)

    if homes != 1:
        raise AssemblyError(
            f"{name} catalog must define exactly one home"
        )

    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise AssemblyError(f"{name} catalog assets must be an array")

    assets: list[dict[str, Any]] = []
    asset_sources: list[PurePosixPath] = []
    asset_destinations: list[PurePosixPath] = []
    for index, raw in enumerate(raw_assets):
        field = f"{name}.assets[{index}]"
        if (
            not isinstance(raw, dict)
            or set(raw) != {"source", "destination", "optional"}
        ):
            raise AssemblyError(
                f"{field} must contain source, destination, and optional"
            )
        source = legacy.safe_path(raw["source"], f"{field}.source")
        destination = legacy.safe_path(
            raw["destination"],
            f"{field}.destination",
        )
        if not isinstance(raw["optional"], bool):
            raise AssemblyError(f"{field}.optional must be boolean")
        asset_sources.append(source)
        asset_destinations.append(destination)
        assets.append(
            {
                "source": source,
                "destination": destination,
                "optional": raw["optional"],
            }
        )

    if len(set(asset_sources)) != len(asset_sources):
        raise AssemblyError(
            f"{name} catalog asset sources must be unique"
        )
    legacy.reject_overlapping_paths(
        asset_sources,
        f"{name} catalog asset sources",
    )
    if len(set(asset_destinations)) != len(asset_destinations):
        raise AssemblyError(
            f"{name} catalog asset destinations must be unique"
        )
    legacy.reject_overlapping_paths(
        asset_destinations,
        f"{name} catalog asset destinations",
    )

    try:
        glossary_source_from_catalog(root)
    except GlossaryError as exc:
        raise AssemblyError(f"{name} catalog glossary is invalid: {exc}") from exc

    return documents, assets


def main() -> int:
    legacy.load_catalog = load_catalog
    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())
