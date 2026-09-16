#!/usr/bin/env python3
"""Render locale overlays on top of the canonical English guided-navigation graph."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
if __package__ in (None, ""):
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import argparse
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

try:
    from scripts.generate_index_navigation import IndexNavigationError, parse_providers
    from scripts.generate_index_navigation_viewer import (
        PROVIDER_ORDER,
        ROOT_INDEX,
        IndexNavigationViewerError,
        _section_level,
        _section_title,
        edge_href,
        github_url,
        heading_anchors,
        immutable_target_url,
        index_page_path,
        index_page_url,
        load_graph,
        page_shell,
        provider_render_indexes,
        published_maps,
        validate_provider_graph,
    )
    from scripts.generate_repository_trees import (
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        published_url,
    )
except ModuleNotFoundError:
    from generate_index_navigation import IndexNavigationError, parse_providers
    from generate_index_navigation_viewer import (
        PROVIDER_ORDER,
        ROOT_INDEX,
        IndexNavigationViewerError,
        _section_level,
        _section_title,
        edge_href,
        github_url,
        heading_anchors,
        immutable_target_url,
        index_page_path,
        index_page_url,
        load_graph,
        page_shell,
        provider_render_indexes,
        published_maps,
        validate_provider_graph,
    )
    from generate_repository_trees import (
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        published_url,
    )

from site_renderer.guided_locales import (
    LocaleViewerError,
    validate_language,
    is_japanese,
    safe_markdown_destination,
    existing_directory_without_symlinks,
    localized_guided_root,
    remove_generated_guided_root,
    read_json,
    load_overlays,
    load_reader_translations,
    locale_index_url,
    locale_index_path,
    translated_edge_href,
    localized_shell,
    path_chain,
    render_localized_edge,
    render_localized_index,
    render_localized_landing,
    write_pair_map,
    LANGUAGE_TAG,
    JA_STRINGS,
    ROUTE_LABELS_JA,
)











































def generate_localized_viewer(
    repository: str,
    graph: dict[str, Any],
    overlays: dict[str, dict[str, dict[str, dict[str, Any]]]],
    reader_translations: dict[tuple[str, str, str], str],
    site_root: Path,
    output_root: Path,
    provider_roots: dict[str, Path],
    pair_map: Path,
) -> list[str]:
    if not REPOSITORY.fullmatch(repository) or graph.get("repository") != repository:
        raise LocaleViewerError("repository or graph repository is invalid")
    if tuple(provider_roots) != PROVIDER_ORDER:
        raise LocaleViewerError("providers must be supplied exactly in canonical order")
    revisions: dict[str, str] = {}
    for provider in graph["providers"]:
        validate_provider_graph(provider)
        name = provider["name"]
        if checked_revision(provider_roots[name]) != provider["revision"]:
            raise LocaleViewerError(f"{name} checkout revision does not match graph")
        revisions[name] = provider["revision"]
    published = published_maps(site_root, provider_roots, revisions)
    safe_output_root = existing_directory_without_symlinks(
        output_root,
        "localized guided output root",
    )

    rendered: list[tuple[Path, str]] = []
    pairs: list[dict[str, str]] = []
    messages: list[str] = []
    providers_by_name = {provider["name"]: provider for provider in graph["providers"]}
    guided_roots: dict[str, Path] = {}
    for language, locale in sorted(overlays.items()):
        language = validate_language(language, "guided locale")
        guided_roots[language] = localized_guided_root(safe_output_root, language)
        landing_path = Path(language) / "guided" / "index.html"
        rendered.append((landing_path, render_localized_landing(language, graph, locale)))
        pairs.append(
            {
                "language": language,
                "canonical_path": "guided/index.html",
                "translation_path": landing_path.as_posix(),
            }
        )
        page_count = 1
        for name in PROVIDER_ORDER:
            provider_overlays = locale.get(name, {})
            if not provider_overlays:
                continue
            provider = providers_by_name[name]
            indexes, parents, edges_by_source = provider_render_indexes(provider)
            for source_path, overlay in provider_overlays.items():
                canonical_index = indexes[source_path]
                relative = locale_index_path(language, name, source_path)
                rendered.append(
                    (
                        relative,
                        render_localized_index(
                            language,
                            repository,
                            provider,
                            canonical_index,
                            overlay,
                            provider_overlays,
                            published[name],
                            reader_translations,
                            indexes,
                            parents,
                            edges_by_source[source_path],
                        ),
                    )
                )
                pairs.append(
                    {
                        "language": language,
                        "canonical_path": index_page_path(name, source_path).as_posix(),
                        "translation_path": relative.as_posix(),
                    }
                )
                page_count += 1
        messages.append(f"generated {page_count} localized guided pages for {language}")

    destinations = [relative for relative, _ in rendered]
    if len(destinations) != len(set(destinations)):
        raise LocaleViewerError("localized guided destinations collide")
    written_roots: set[Path] = set()
    try:
        for language, guided_root in guided_roots.items():
            locale_root = safe_output_root / language
            if locale_root.is_symlink():
                raise LocaleViewerError(
                    f"localized guided locale parent became a symlink: {locale_root}"
                )
            guided_root.mkdir(parents=True, exist_ok=False)
            if guided_root.is_symlink():
                raise LocaleViewerError(
                    f"localized guided destination became a symlink: {guided_root}"
                )
            written_roots.add(guided_root)
        for relative, content in rendered:
            destination = safe_output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        write_pair_map(pair_map, pairs)
    except BaseException:
        for root in written_roots:
            remove_generated_guided_root(root, safe_output_root)
        raise
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--locale-overlays", required=True, type=Path)
    parser.add_argument("--translation-map", required=True, type=Path)
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--pair-map", required=True, type=Path)
    parser.add_argument("--provider", action="append", default=[])
    args = parser.parse_args()
    try:
        provider_roots = parse_providers(args.provider)
        graph = load_graph(args.graph)
        overlays = load_overlays(args.locale_overlays, graph)
        reader_translations = load_reader_translations(args.translation_map)
        messages = generate_localized_viewer(
            args.repository,
            graph,
            overlays,
            reader_translations,
            args.site_root,
            args.output_root,
            provider_roots,
            args.pair_map,
        )
    except (
        IndexNavigationError,
        IndexNavigationViewerError,
        LocaleViewerError,
        RepositoryTreeError,
        ValueError,
        OSError,
    ) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
