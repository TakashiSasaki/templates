#!/usr/bin/env python3
"""Render the immutable provider index navigation graph as static HTML."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit

try:
    from scripts.generate_index_navigation import (
        PROVIDER_ORDER,
        ROOT_INDEX,
        IndexNavigationError,
        collect_provider_graph,
        contains_disallowed_control,
        immutable_git,
        parse_providers,
        validate_external_location,
    )
    from scripts.generate_repository_browser import viewer_relative_url
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        github_url,
        manifest_destinations,
        published_url,
    )
except ModuleNotFoundError:
    from generate_index_navigation import (
        PROVIDER_ORDER,
        ROOT_INDEX,
        IndexNavigationError,
        collect_provider_graph,
        contains_disallowed_control,
        immutable_git,
        parse_providers,
        validate_external_location,
    )
    from generate_repository_browser import viewer_relative_url
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        github_url,
        manifest_destinations,
        published_url,
    )


from site_renderer.guided import (
    prepare_guided_root,
    encoded_path,
    index_page_path,
    index_page_url,
    fragment_suffix,
    heading_anchor,
    heading_anchors,
    immutable_edge_path,
    edge_href,
    immutable_target_url,
    provider_render_indexes,
    canonical_parent_map,
    breadcrumb_chain,
    page_shell,
    render_edge,
    render_index_page,
    render_landing,
    validate_render_destinations,
    GUIDED_ROOT,
    ROOT_INDEX_NAMESPACE,
    MARKER,
    MARKER_CONTENT,
    IDCOUNT_RE,
)


from publication_bundle.graph import (
    IndexNavigationViewerError,
    contains_non_scalar,
    load_graph,
    validate_repository_path,
    is_index_source_path,
    validate_plain_heading,
    _section_title,
    _section_level,
    validate_provider_graph,
)


















from publication_bundle import graph as _graph_contract


def validate_provider_graph(provider):
    return _graph_contract.validate_provider_graph(provider, provider_order=PROVIDER_ORDER)


def load_graph(path):
    return _graph_contract.load_graph(path, provider_order=PROVIDER_ORDER)
















def published_maps(
    site_root: Path,
    provider_roots: dict[str, Path],
    revisions: dict[str, str],
) -> dict[str, dict[str, str]]:
    try:
        destinations = manifest_destinations(site_root)
    except RepositoryTreeError as exc:
        raise IndexNavigationViewerError(
            f"unable to resolve site manifest destinations: {exc}"
        ) from exc

    result: dict[str, dict[str, str]] = {}
    for provider in PROVIDER_ORDER:
        revision = revisions.get(provider)
        if revision is None or not FULL_SHA.fullmatch(revision):
            raise IndexNavigationViewerError(f"{provider} revision is invalid")
        try:
            raw_catalog = immutable_git(
                provider_roots[provider],
                "show",
                f"{revision}:docs/publication-catalog.json",
            )
            catalog = json.loads(raw_catalog.decode("utf-8", errors="strict"))
        except (IndexNavigationError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IndexNavigationViewerError(
                f"unable to read immutable {provider} publication catalog: {exc}"
            ) from exc
        if not isinstance(catalog, dict):
            raise IndexNavigationViewerError(
                f"{provider} publication catalog must be an object"
            )
        documents = catalog.get("documents")
        if not isinstance(documents, list):
            raise IndexNavigationViewerError(
                f"{provider} publication catalog documents must be an array"
            )
        decoded: dict[str, str] = {}
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                raise IndexNavigationViewerError(
                    f"{provider} publication catalog document {index} must be an object"
                )
            document_id = document.get("id")
            source = document.get("source")
            if not isinstance(document_id, str) or not isinstance(source, str):
                raise IndexNavigationViewerError(
                    f"{provider} publication catalog document {index} is invalid"
                )
            destination = destinations.get((provider, document_id))
            if destination is None:
                raise IndexNavigationViewerError(
                    f"site manifest does not map {provider}:{document_id}"
                )
            decoded[source] = destination
        result[provider] = decoded
    return result
























def verify_index_objects(provider: dict[str, Any], provider_root: Path) -> None:
    """Verify the supplied provider graph is exactly derived from the locked revision."""
    try:
        expected = collect_provider_graph(provider["name"], provider_root)
    except IndexNavigationError as exc:
        raise IndexNavigationViewerError(
            f"unable to regenerate immutable {provider['name']} graph: {exc}"
        ) from exc

    expected_indexes = {
        index["path"]: index
        for index in expected["indexes"]
        if isinstance(index, dict) and isinstance(index.get("path"), str)
    }
    for index in provider["indexes"]:
        expected_index = expected_indexes.get(index["path"])
        if expected_index is None or expected_index.get("object_id") != index["object_id"]:
            raise IndexNavigationViewerError(
                f"{provider['name']} index object does not match locked revision: "
                f"{index['path']}"
            )

    if expected != provider:
        raise IndexNavigationViewerError(
            f"{provider['name']} graph content does not match locked revision"
        )


def generate_viewer(
    repository: str,
    graph: dict[str, Any],
    site_root: Path,
    output_root: Path,
    provider_roots: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise IndexNavigationViewerError("repository must use owner/name syntax")
    if graph.get("repository") != repository:
        raise IndexNavigationViewerError("graph repository does not match requested repository")
    if tuple(provider_roots) != PROVIDER_ORDER:
        raise IndexNavigationViewerError(
            "providers must be supplied exactly in this order: " + ", ".join(PROVIDER_ORDER)
        )
    if site_root.is_symlink() or not site_root.is_dir():
        raise IndexNavigationViewerError("site root must be a directory")
    if output_root.is_symlink() or not output_root.is_dir():
        raise IndexNavigationViewerError("output root must be an existing directory")

    revisions: dict[str, str] = {}
    for provider in graph["providers"]:
        validate_provider_graph(provider)
        name = provider["name"]
        actual = checked_revision(provider_roots[name])
        if actual != provider["revision"]:
            raise IndexNavigationViewerError(
                f"{name} graph revision {provider['revision']} does not match checkout {actual}"
            )
        revisions[name] = provider["revision"]

    published = published_maps(site_root, provider_roots, revisions)
    landing = render_landing(graph)
    rendered: list[tuple[Path, str]] = []
    messages: list[str] = []
    for provider in graph["providers"]:
        name = provider["name"]
        indexes, parents, edges_by_source = provider_render_indexes(provider)
        for index in provider["indexes"]:
            source_path = index["path"]
            relative = index_page_path(name, source_path)
            rendered.append(
                (
                    relative,
                    render_index_page(
                        repository,
                        provider,
                        index,
                        published[name],
                        edges_by_source[source_path],
                        indexes,
                        parents,
                    ),
                )
            )
        messages.append(
            f"generated guided navigation for {name} @ {provider['revision']} "
            f"({len(provider['indexes'])} index pages)"
        )

    validate_render_destinations([relative for relative, _content in rendered])
    for provider in graph["providers"]:
        verify_index_objects(provider, provider_roots[provider["name"]])

    guided: Path | None = None
    try:
        guided = prepare_guided_root(output_root)
        (guided / "graph.json").write_text(
            json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (guided / "index.html").write_text(landing, encoding="utf-8")
        for relative, content in rendered:
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
    except BaseException:
        if guided is not None:
            shutil.rmtree(guided, ignore_errors=True)
        raise
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--provider", action="append", default=[])
    args = parser.parse_args()
    try:
        providers = parse_providers(args.provider)
        graph = load_graph(args.graph)
        messages = generate_viewer(
            args.repository,
            graph,
            args.site_root,
            args.output_root,
            providers,
        )
    except (
        IndexNavigationError,
        IndexNavigationViewerError,
        RepositoryTreeError,
        OSError,
    ) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())