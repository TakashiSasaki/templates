#!/usr/bin/env python3
"""Rebase canonical provider links onto Site publication destinations.

Provider Markdown is authoritative in its source tree, where relative links are
resolved against canonical repository paths. The Site manifest is free to map
those cataloged documents into a reader-oriented URL hierarchy. This module
bridges those two coordinate systems after assembly without modifying provider
source files.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, unquote

from scripts.assemble_publications import (
    AssemblyError,
    load_catalog,
    load_manifest,
    resolve,
)
from scripts.generate_repository_trees import (
    RepositoryTreeError,
    entry_label,
    read_entries,
)

from publication_bundle.markdown import (
    SCHEME,
    FENCE,
    REFERENCE,
    AssetRule,
    _normalise_source_path,
    _split_destination,
    _asset_target,
    _rewrite_destination,
    _inline_code_spans,
    _in_spans,
    _rewrite_inline_links,
    _rewrite_reference_definition,
    _rewrite_markdown,
)





















def rebase_publication_links(
    publication_roots: dict[str, Path],
    site_root: Path,
    output_root: Path,
    *,
    site_source_root: Path | None = None,
) -> int:
    """Rewrite published relative links that target declared provider outputs."""
    site_root = site_root.resolve(strict=True)
    output_root = output_root.resolve(strict=True)
    docs_root = output_root / "docs"

    catalogs: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ] = {}
    for name, root in sorted(publication_roots.items()):
        resolved_root = root.resolve(strict=True)
        documents, assets = load_catalog(name, resolved_root)
        catalogs[name] = (resolved_root, documents, assets)

    site_source_paths: frozenset[bytes] | None = None
    if "site" in catalogs:
        if site_source_root is None:
            raise AssemblyError(
                "original Site source root is required for Source-browser link identity"
            )
        try:
            site_entries = read_entries(site_source_root.resolve(strict=True))
        except RepositoryTreeError as exc:
            raise AssemblyError(str(exc)) from exc
        site_source_paths = frozenset(
            entry.path for entry in site_entries if entry_label(entry) == "file"
        )

    manifest = load_manifest(site_root / "site-manifest.json")
    canonical_documents = manifest.documents

    document_targets: dict[str, dict[PurePosixPath, PurePosixPath]] = {
        name: {} for name in catalogs
    }
    for page in canonical_documents:
        publication = page["publication"]
        _, documents, _ = catalogs[publication]
        source = documents[page["document"]]["source"]
        destination = page["destination"]
        if docs_root.joinpath(*destination.parts).is_file():
            document_targets[publication][source] = destination

    asset_rules: dict[str, list[AssetRule]] = {name: [] for name in catalogs}
    for name, (root, _, assets) in catalogs.items():
        for asset in assets:
            source = resolve(root, asset["source"], f"{name} asset")
            if not source.exists():
                continue
            destination = PurePosixPath(name) / asset["destination"]
            asset_rules[name].append(
                (asset["source"], destination, source.is_dir())
            )

    total = 0
    for page in canonical_documents:
        publication = page["publication"]
        publication_root, documents, _ = catalogs[publication]
        source_document = documents[page["document"]]["source"]
        site_document = page["destination"]
        target = docs_root.joinpath(*site_document.parts)
        if not target.is_file():
            continue

        original = target.read_text(encoding="utf-8")
        updated, count = _rewrite_markdown(
            original,
            source_document=source_document,
            site_document=site_document,
            document_targets=document_targets[publication],
            asset_rules=asset_rules[publication],
            docs_root=docs_root,
            publication=publication,
            site_source_paths=site_source_paths,
        )
        if count:
            target.write_text(updated, encoding="utf-8")
            total += count

    return total
