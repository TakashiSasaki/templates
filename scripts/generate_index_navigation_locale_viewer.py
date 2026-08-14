#!/usr/bin/env python3
"""Render locale overlays on top of the canonical English guided-navigation graph."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
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


class LocaleViewerError(RuntimeError):
    """Raised when localized guided navigation cannot be rendered safely."""


JA_STRINGS = {
    "page_path": "ページパス:",
    "eyebrow": "インデックスに沿ったナビゲーション",
    "notice": "この表示は、固定された正確な revision における provider 所有の index.md ナビゲーションを、日本語の参考訳で表示します。リンク先、順序、到達可能性、階層構造は英語正本のナビゲーショングラフが唯一の権威です。",
    "provider": "Provider",
    "revision": "Revision",
    "source": "Source",
    "immutable_source": "不変の GitHub ソース",
    "repository": "Repository",
    "browse_snapshot": "同じスナップショットを閲覧",
    "before_section": "最初の provider section より前のリンク",
    "no_links": "この section にはリンクがありません。",
    "human_agent": "人間 / エージェント共有経路",
    "landing_title": "インデックスに沿った文書探索",
    "landing_notice": "AI エージェントが検索へフォールバックする前に利用できる provider 所有の index.md 構造と同じ経路を辿ります。この日本語表示は不変の provider revision と英語正本グラフから生成され、Site が定義する reader navigation とは分離されています。",
    "inspect_graph": "機械可読ナビゲーショングラフを確認",
    "browse_all": "すべてのソーススナップショットを閲覧",
    "reachable": "到達可能な index",
    "links": "リンク",
    "depth": "最大 index 深度",
    "browse_same": "同じリポジトリスナップショットを閲覧",
    "index_line": "index 行",
    "immutable_source_short": "不変ソース",
}

ROUTE_LABELS_JA = {
    "index": "index",
    "same index": "同じ index",
    "external": "外部",
    "repository directory": "リポジトリディレクトリ",
    "immutable directory": "不変ディレクトリ",
    "published document": "公開文書",
    "immutable source": "不変ソース",
    "source file": "ソースファイル",
}


def read_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise LocaleViewerError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocaleViewerError(f"unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LocaleViewerError(f"{label} must be an object")
    return value


def load_overlays(path: Path, graph: dict[str, Any]) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    data = read_json(path, "guided locale overlay")
    if set(data) != {
        "schema_version",
        "canonical_graph_schema_version",
        "canonical_language",
        "locales",
    }:
        raise LocaleViewerError("guided locale overlay has unsupported fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise LocaleViewerError("guided locale overlay schema_version must be integer 1")
    if data["canonical_graph_schema_version"] != graph.get("schema_version"):
        raise LocaleViewerError("guided locale overlay does not match graph schema")
    if data["canonical_language"] != "en":
        raise LocaleViewerError("guided locale overlay canonical_language must be en")
    locales = data["locales"]
    if not isinstance(locales, list):
        raise LocaleViewerError("guided locale overlay locales must be an array")

    graph_providers = {provider["name"]: provider for provider in graph["providers"]}
    result: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for locale_index, locale in enumerate(locales):
        if not isinstance(locale, dict) or set(locale) != {"language", "providers"}:
            raise LocaleViewerError(f"locales[{locale_index}] is invalid")
        language = locale["language"]
        providers = locale["providers"]
        if not isinstance(language, str) or not language or language == "en":
            raise LocaleViewerError(f"locales[{locale_index}].language is invalid")
        if language in result:
            raise LocaleViewerError(f"duplicate guided locale: {language}")
        if not isinstance(providers, list):
            raise LocaleViewerError(f"locales[{locale_index}].providers must be an array")
        locale_result: dict[str, dict[str, dict[str, Any]]] = {}
        for provider_index, provider in enumerate(providers):
            if not isinstance(provider, dict) or set(provider) != {"name", "revision", "indexes"}:
                raise LocaleViewerError(
                    f"locales[{locale_index}].providers[{provider_index}] is invalid"
                )
            name = provider["name"]
            canonical_provider = graph_providers.get(name)
            if canonical_provider is None or provider["revision"] != canonical_provider["revision"]:
                raise LocaleViewerError(f"locale provider revision mismatch: {name}")
            indexes = provider["indexes"]
            if not isinstance(indexes, list):
                raise LocaleViewerError(f"locale provider indexes must be an array: {name}")
            canonical_indexes = {
                index["path"]: index for index in canonical_provider["indexes"]
            }
            index_result: dict[str, dict[str, Any]] = {}
            for index in indexes:
                if not isinstance(index, dict) or set(index) != {"path", "title", "sections", "links"}:
                    raise LocaleViewerError(f"localized index record is invalid: {name}")
                path_value = index["path"]
                if path_value not in canonical_indexes or path_value in index_result:
                    raise LocaleViewerError(f"localized index path is invalid or duplicate: {name}:{path_value}")
                sections = index["sections"]
                links = index["links"]
                if not isinstance(sections, list) or not isinstance(links, list):
                    raise LocaleViewerError(f"localized index prose is invalid: {name}:{path_value}")
                if len(sections) != len(canonical_indexes[path_value]["sections"]):
                    raise LocaleViewerError(f"localized section count drift: {name}:{path_value}")
                source_edges = [
                    edge for edge in canonical_provider["edges"] if edge["source"] == path_value
                ]
                if len(links) != len(source_edges):
                    raise LocaleViewerError(f"localized link count drift: {name}:{path_value}")
                index_result[path_value] = index
            locale_result[name] = index_result
        result[language] = locale_result
    return result


def load_reader_translations(path: Path) -> dict[tuple[str, str, str], str]:
    data = read_json(path, "reader translation publication map")
    if set(data) != {"schema_version", "canonical_language", "translations"}:
        raise LocaleViewerError("reader translation publication map has unsupported fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise LocaleViewerError("reader translation publication map schema_version must be integer 1")
    if data["canonical_language"] != "en" or not isinstance(data["translations"], list):
        raise LocaleViewerError("reader translation publication map is invalid")
    result: dict[tuple[str, str, str], str] = {}
    for record in data["translations"]:
        if not isinstance(record, dict):
            raise LocaleViewerError("reader translation publication record must be an object")
        required = {
            "publication",
            "language",
            "canonical_destination",
            "translation_destination",
        }
        if set(record) != required:
            raise LocaleViewerError("reader translation publication record has unsupported fields")
        key = (
            record["language"],
            record["publication"],
            record["canonical_destination"],
        )
        if not all(isinstance(value, str) and value for value in key) or key in result:
            raise LocaleViewerError("reader translation publication record is invalid or duplicate")
        destination = record["translation_destination"]
        if not isinstance(destination, str) or not destination:
            raise LocaleViewerError("reader translation destination is invalid")
        result[key] = destination
    return result


def locale_index_url(language: str, provider: str, source_path: str) -> str:
    return f"/{quote(language, safe='')}" + index_page_url(provider, source_path)


def locale_index_path(language: str, provider: str, source_path: str) -> Path:
    return Path(language) / index_page_path(provider, source_path)


def translated_edge_href(
    language: str,
    repository: str,
    provider: dict[str, Any],
    edge: dict[str, Any],
    published: dict[str, str],
    overlay_indexes: dict[str, dict[str, Any]],
    reader_translations: dict[tuple[str, str, str], str],
) -> tuple[str, str, bool]:
    kind = edge["kind"]
    target = edge["target"]
    fragment = edge.get("fragment")
    if kind == "index" and target in overlay_indexes:
        suffix = "" if fragment is None else "#" + quote(fragment, safe="-._~:/")
        return locale_index_url(language, provider["name"], target) + suffix, "index", False
    if kind == "fragment":
        suffix = "" if fragment is None else "#" + quote(fragment, safe="-._~:/")
        return suffix, "same index", False
    if kind == "file":
        canonical_destination = published.get(target)
        if canonical_destination is not None:
            translated_destination = reader_translations.get(
                (language, provider["name"], canonical_destination)
            )
            if translated_destination is not None:
                suffix = "" if fragment is None else "#" + quote(fragment, safe="-._~:/")
                return (
                    published_url("/", translated_destination) + suffix,
                    "published document",
                    False,
                )
    return edge_href(
        provider["name"],
        provider["revision"],
        edge,
        published,
        repository,
    )


def localized_shell(title: str, body: str, page_path: str, language: str) -> str:
    source = page_shell(title, body, page_path)
    source = source.replace('<html lang="en">', f'<html lang="{html.escape(language, quote=True)}">', 1)
    if language.startswith("ja"):
        source = source.replace("Page path:", JA_STRINGS["page_path"], 1)
    return source


def path_chain(
    current: str,
    parents: dict[str, tuple[str, str]],
) -> list[str]:
    chain = [current]
    seen = {current}
    while chain[-1] != ROOT_INDEX:
        parent = parents.get(chain[-1])
        if parent is None or parent[0] in seen:
            break
        seen.add(parent[0])
        chain.append(parent[0])
    chain.reverse()
    return chain


def render_localized_edge(
    language: str,
    repository: str,
    provider: dict[str, Any],
    edge: dict[str, Any],
    localized: dict[str, str],
    published: dict[str, str],
    overlay_indexes: dict[str, dict[str, Any]],
    reader_translations: dict[tuple[str, str, str], str],
) -> str:
    href, route_kind, external = translated_edge_href(
        language,
        repository,
        provider,
        edge,
        published,
        overlay_indexes,
        reader_translations,
    )
    source = immutable_target_url(repository, provider["revision"], edge)
    attrs = ' target="_blank" rel="noopener"' if external else ""
    origin = github_url(
        repository,
        provider["revision"],
        "blob",
        edge["source"].encode("utf-8"),
    ) + f"#L{edge['line']}"
    metadata = [
        f'<span class="badge">{html.escape(ROUTE_LABELS_JA.get(route_kind, route_kind) if language.startswith("ja") else route_kind)}</span>',
        f'<a href="{html.escape(origin, quote=True)}" target="_blank" rel="noopener">{JA_STRINGS["index_line"] if language.startswith("ja") else "index line"} {edge["line"]}</a>',
    ]
    if source is not None:
        label = JA_STRINGS["immutable_source_short"] if language.startswith("ja") else "immutable source"
        metadata.append(
            f'<a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">{html.escape(label)}</a>'
        )
    return (
        '<li class="link-card">'
        f'<a href="{html.escape(href, quote=True)}"{attrs}><strong>{html.escape(localized["label"])}</strong></a>'
        f'<p>{html.escape(localized["description"])}</p>'
        f'<div class="link-meta">{" · ".join(metadata)}</div>'
        "</li>"
    )


def render_localized_index(
    language: str,
    repository: str,
    provider: dict[str, Any],
    canonical_index: dict[str, Any],
    overlay: dict[str, Any],
    overlay_indexes: dict[str, dict[str, Any]],
    published: dict[str, str],
    reader_translations: dict[tuple[str, str, str], str],
    indexes: dict[str, dict[str, Any]],
    parents: dict[str, tuple[str, str]],
    edges: list[dict[str, Any]],
) -> str:
    source_path = canonical_index["path"]
    source = github_url(
        repository,
        provider["revision"],
        "blob",
        source_path.encode("utf-8"),
    )
    breadcrumbs = []
    for path in path_chain(source_path, parents):
        path_overlay = overlay_indexes.get(path)
        title = path_overlay["title"] if path_overlay is not None else indexes[path]["title"]
        url = (
            locale_index_url(language, provider["name"], path)
            if path_overlay is not None
            else index_page_url(provider["name"], path)
        )
        breadcrumbs.append((title, url))
    breadcrumb_html = "".join(
        f'<span><a href="{html.escape(url, quote=True)}">{html.escape(title)}</a></span>'
        for title, url in breadcrumbs
    )

    localized_sections = overlay["sections"]
    heading_ids = heading_anchors(
        [overlay["title"], *[section["title"] for section in localized_sections]]
    )
    localized_links = overlay["links"]
    edge_pairs = list(zip(edges, localized_links, strict=True))
    unsectioned = [pair for pair in edge_pairs if pair[0].get("section") is None]
    by_section: dict[str, list[tuple[dict[str, Any], dict[str, str]]]] = {}
    for edge, localized in edge_pairs:
        if edge.get("section") is not None:
            by_section.setdefault(edge["section"], []).append((edge, localized))

    ja = language.startswith("ja")
    strings = JA_STRINGS
    body_parts = [
        f'<p class="eyebrow">{html.escape(strings["eyebrow"] if ja else "Index-guided navigation")}</p>',
        f'<h1 id="{html.escape(heading_ids[0], quote=True)}">{html.escape(overlay["title"])}</h1>',
        f'<p class="notice">{html.escape(strings["notice"] if ja else "This localized view projects non-authoritative translated prose onto the canonical English navigation graph.")}</p>',
        f'<nav class="breadcrumbs" aria-label="Index path">{breadcrumb_html}</nav>',
        '<div class="meta">',
        f'<p><strong>{html.escape(strings["provider"] if ja else "Provider")}:</strong> <code>{html.escape(provider["name"])}</code></p>',
        f'<p><strong>{html.escape(strings["revision"] if ja else "Revision")}:</strong> <code>{html.escape(provider["revision"])}</code></p>',
        f'<p><strong>{html.escape(strings["source"] if ja else "Source")}:</strong> <code>{html.escape(source_path)}</code> · <a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">{html.escape(strings["immutable_source"] if ja else "immutable GitHub source")}</a></p>',
        f'<p><strong>{html.escape(strings["repository"] if ja else "Repository")}:</strong> <a href="/files/{quote(provider["name"], safe="")}/">{html.escape(strings["browse_snapshot"] if ja else "browse the same snapshot")}</a></p>',
        "</div>",
    ]
    if unsectioned:
        label = strings["before_section"] if ja else "Links before the first provider section"
        body_parts.append(
            '<div class="section" aria-label="Links before the first provider section">'
            f'<p class="eyebrow">{html.escape(label)}</p><ul class="link-list">'
        )
        for edge, localized in unsectioned:
            body_parts.append(
                render_localized_edge(
                    language,
                    repository,
                    provider,
                    edge,
                    localized,
                    published,
                    overlay_indexes,
                    reader_translations,
                )
            )
        body_parts.append("</ul></div>")

    canonical_sections = canonical_index["sections"]
    for section_number, (canonical_section, localized_section) in enumerate(
        zip(canonical_sections, localized_sections, strict=True), start=1
    ):
        canonical_title = _section_title(canonical_section)
        level = _section_level(canonical_section)
        body_parts.append(
            f'<section class="section"><h{level} id="{html.escape(heading_ids[section_number], quote=True)}">{html.escape(localized_section["title"])}</h{level}>'
        )
        pairs = by_section.get(canonical_title, [])
        if pairs:
            body_parts.append('<ul class="link-list">')
            for edge, localized in pairs:
                body_parts.append(
                    render_localized_edge(
                        language,
                        repository,
                        provider,
                        edge,
                        localized,
                        published,
                        overlay_indexes,
                        reader_translations,
                    )
                )
            body_parts.append("</ul>")
        else:
            body_parts.append(
                f'<p><em>{html.escape(strings["no_links"] if ja else "No links in this section.")}</em></p>'
            )
        body_parts.append("</section>")

    return localized_shell(
        overlay["title"],
        "\n".join(body_parts),
        locale_index_url(language, provider["name"], source_path),
        language,
    )


def render_localized_landing(
    language: str,
    graph: dict[str, Any],
    locale: dict[str, dict[str, dict[str, Any]]],
) -> str:
    ja = language.startswith("ja")
    strings = JA_STRINGS
    cards = []
    for provider in graph["providers"]:
        name = provider["name"]
        diagnostics = provider["diagnostics"]
        root_overlay = locale.get(name, {}).get(ROOT_INDEX)
        target = (
            locale_index_url(language, name, ROOT_INDEX)
            if root_overlay is not None
            else index_page_url(name, ROOT_INDEX)
        )
        cards.append(
            '<section class="provider-card">'
            f'<h2><a href="{html.escape(target, quote=True)}">{html.escape(name)}</a></h2>'
            f'<p><code>{html.escape(provider["revision"])}</code></p>'
            f'<p>{diagnostics["index_count"]} {html.escape(strings["reachable"] if ja else "reachable indexes")} · '
            f'{diagnostics["edge_count"]} {html.escape(strings["links"] if ja else "links")} · '
            f'{html.escape(strings["depth"] if ja else "maximum index depth")} {diagnostics["max_index_depth"]}</p>'
            f'<p><a href="/files/{quote(name, safe="")}/">{html.escape(strings["browse_same"] if ja else "Browse the same repository snapshot")}</a></p>'
            "</section>"
        )
    body = "\n".join(
        [
            f'<p class="eyebrow">{html.escape(strings["human_agent"] if ja else "Human / agent shared path")}</p>',
            f'<h1>{html.escape(strings["landing_title"] if ja else "Index-guided document discovery")}</h1>',
            f'<p class="notice">{html.escape(strings["landing_notice"] if ja else "This localized view follows the canonical provider-owned index navigation graph.")}</p>',
            f'<p><a href="/guided/graph.json">{html.escape(strings["inspect_graph"] if ja else "Inspect the machine-readable navigation graph")}</a> · <a href="/files/">{html.escape(strings["browse_all"] if ja else "Browse all source snapshots")}</a></p>',
            f'<div class="provider-grid">{"".join(cards)}</div>',
        ]
    )
    return localized_shell(
        strings["landing_title"] if ja else "Index-guided document discovery",
        body,
        f"/{quote(language, safe='')}/guided/",
        language,
    )


def write_pair_map(path: Path, pairs: list[dict[str, str]]) -> None:
    if path.is_symlink():
        raise LocaleViewerError("guided locale publication map must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "canonical_language": "en",
                "pages": pairs,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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

    rendered: list[tuple[Path, str]] = []
    pairs: list[dict[str, str]] = []
    messages: list[str] = []
    providers_by_name = {provider["name"]: provider for provider in graph["providers"]}
    for language, locale in sorted(overlays.items()):
        guided_root = output_root / language / "guided"
        if guided_root.exists() or guided_root.is_symlink():
            raise LocaleViewerError(f"localized guided destination already exists: {guided_root}")
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
        for relative, content in rendered:
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            written_roots.add(output_root / relative.parts[0] / "guided")
            destination.write_text(content, encoding="utf-8")
        write_pair_map(pair_map, pairs)
    except BaseException:
        import shutil

        for root in written_roots:
            shutil.rmtree(root, ignore_errors=True)
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
        OSError,
    ) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
