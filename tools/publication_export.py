"""Validate Modeling's bounded publication export without fetching subjects."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import catalog as record_catalog


class ExportError(ValueError):
    pass


def _json(root: Path, relative: str) -> dict:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ExportError(f"{relative} must be a regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExportError(f"{relative} must be an object")
    return value


def _safe(value: object, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ExportError(f"{field} must be a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise ExportError(f"{field} must be a safe relative POSIX path")
    return path


def validate(root: Path) -> None:
    # The exported records are locally authored administrative metadata.  Run
    # the canonical offline record validator here so a publication export can
    # never turn an arbitrary external payload into a record asset.
    record_catalog.load(root)
    publication_catalog = _json(root, "docs/publication-catalog.json")
    if publication_catalog.get("schema_version") != 4 or set(publication_catalog) != {"schema_version", "documents", "assets"}:
        raise ExportError("publication catalog must be schema version 4")
    documents = publication_catalog["documents"]
    assets = publication_catalog["assets"]
    if not isinstance(documents, list) or not documents or not isinstance(assets, list):
        raise ExportError("publication catalog documents/assets are invalid")
    homes = [item for item in documents if isinstance(item, dict) and item.get("home") is True]
    if len(homes) != 1:
        raise ExportError("publication catalog must have exactly one home document")
    for index, item in enumerate(documents):
        if not isinstance(item, dict) or set(item) != {"id", "source", "optional", "home"}:
            raise ExportError(f"documents[{index}] has an invalid shape")
        source = _safe(item["source"], f"documents[{index}].source")
        path = root / source
        if not path.is_file() or path.is_symlink():
            raise ExportError(f"document source is not regular: {source}")
    destinations: list[PurePosixPath] = []
    record_assets = []
    for index, item in enumerate(assets):
        if not isinstance(item, dict) or set(item) != {"source", "destination", "optional", "source_kind"}:
            raise ExportError(f"assets[{index}] has an invalid shape")
        source = _safe(item["source"], f"assets[{index}].source")
        destination = _safe(item["destination"], f"assets[{index}].destination")
        if item["source_kind"] != "tracked":
            raise ExportError("Modeling export only permits tracked assets")
        if item["source"] == "records":
            record_assets.append(item)
            if item["destination"] != "records":
                raise ExportError("record metadata must retain the records destination")
        path = root / source
        if not path.exists() or path.is_symlink():
            raise ExportError(f"asset source is not a regular tree: {source}")
        destinations.append(destination)
    for left_index, left in enumerate(destinations):
        for right in destinations[left_index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise ExportError("asset destinations overlap")
    declaration = _json(root, "docs/publication-capabilities.json")
    if declaration.get("schema_version") != 1 or declaration.get("provider") != "modeling":
        raise ExportError("publication capability declaration is not Modeling-owned")
    record_exports = [item for item in declaration.get("exports", [])
                      if isinstance(item, dict) and item.get("kind") == "record"]
    if len(record_assets) != 1 or len(record_exports) != 1:
        raise ExportError("the bounded export must declare exactly one local record metadata tree")
    record_export = record_exports[0]
    if (set(record_export) != {"kind", "namespace", "media_type", "identity_basis",
                               "feature", "subject_ownership", "redistribution"}
            or record_export["subject_ownership"] != "external-as-recorded"
            or record_export["redistribution"] != "local-record-metadata"):
        raise ExportError("record export must separate external subject ownership from local metadata redistribution")


if __name__ == "__main__":
    validate(Path(__file__).resolve().parents[1])
