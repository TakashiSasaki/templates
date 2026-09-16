"""Upstream-only immutable Git inspection and bounded source read models."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Iterable
from publication_bundle.repository import *
from integration.publication_model import AssemblyError, load_manifest

from publication_bundle.source_reader import (
    git,
    checked_revision,
    read_entries,
    run_git_batch,
    object_sizes,
    object_contents,
    build_preview_records,
    collect_records,
)






def manifest_destinations(site_root: Path) -> dict[tuple[str, str], str]:
    try:
        manifest = load_manifest(site_root / "site-manifest.json")
    except AssemblyError as exc:
        raise RepositoryTreeError(str(exc)) from exc
    return {
        (document["publication"], document["document"]): document["destination"].as_posix()
        for document in manifest.documents
    }


def published_sources(
    publication: str,
    publication_root: Path,
    site_root: Path,
) -> dict[bytes, str]:
    catalog = read_json(
        publication_root / "docs/publication-catalog.json",
        f"{publication} publication catalog",
    )
    documents = catalog.get("documents")
    if not isinstance(documents, list):
        raise RepositoryTreeError(
            f"{publication} publication catalog documents must be an array"
        )
    destinations = manifest_destinations(site_root)
    result: dict[bytes, str] = {}
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise RepositoryTreeError(
                f"{publication} publication catalog document {index} must be an object"
            )
        document_id = document.get("id")
        source = document.get("source")
        if not isinstance(document_id, str) or not isinstance(source, str):
            raise RepositoryTreeError(
                f"{publication} publication catalog document {index} is invalid"
            )
        destination = destinations.get((publication, document_id))
        if destination is None:
            raise RepositoryTreeError(
                f"site manifest does not map {publication}:{document_id}"
            )
        result[source.encode("utf-8")] = destination
    return result









