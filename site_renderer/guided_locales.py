"""Render localized guided read models; provider freshness is already derived."""
from __future__ import annotations
import html
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote
from publication_bundle.graph import *
from publication_bundle.graph import _section_title, _section_level
from publication_bundle.paths import public_path
from site_renderer.guided import *
from site_renderer.github import github_blob_url, github_commit_url, github_tree_url

from publication_bundle.locales import LANGUAGE_TAG


from publication_bundle.locales import LocaleViewerError


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


from publication_bundle.locales import validate_language


def is_japanese(language: str) -> bool:
    """Return whether the validated locale's primary language subtag is Japanese."""
    return validate_language(language).split("-", 1)[0] == "ja"


def safe_markdown_destination(value: Any, field: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
        raise LocaleViewerError(f"{field} must be a safe relative Markdown path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise LocaleViewerError(f"{field} must be a safe relative Markdown path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.lower() != ".md":
        raise LocaleViewerError(f"{field} must be a safe relative Markdown path")
    return path


def existing_directory_without_symlinks(path: Path, field: str) -> Path:
    """Return an absolute existing directory after rejecting every symlink component."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise LocaleViewerError(f"{field} must not traverse a symlink: {path}")
        if not current.exists():
            raise LocaleViewerError(f"{field} must be an existing directory: {path}")
    if not absolute.is_dir():
        raise LocaleViewerError(f"{field} must be an existing directory: {path}")
    return absolute


def localized_guided_root(output_root: Path, language: str) -> Path:
    """Resolve one not-yet-created locale guided root without following locale symlinks."""
    language = validate_language(language, "guided locale")
    root = existing_directory_without_symlinks(
        output_root,
        "localized guided output root",
    )
    locale_root = root / language
    if locale_root.is_symlink():
        raise LocaleViewerError(
            f"localized guided locale parent must not be a symlink: {locale_root}"
        )
    if locale_root.exists() and not locale_root.is_dir():
        raise LocaleViewerError(
            f"localized guided locale parent must be a directory when present: {locale_root}"
        )
    guided_root = locale_root / "guided"
    if guided_root.exists() or guided_root.is_symlink():
        raise LocaleViewerError(
            f"localized guided destination already exists: {guided_root}"
        )
    return guided_root


def remove_generated_guided_root(root: Path, output_root: Path) -> None:
    """Remove only a generated root whose current parents are still non-symlinks."""
    try:
        relative = root.relative_to(output_root)
    except ValueError:
        return
    current = output_root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            return
    if root.is_symlink():
        return
    if root.is_dir():
        shutil.rmtree(root, ignore_errors=True)


from publication_bundle.locales import read_json


from publication_bundle.locales import load_overlays


def load_reader_translations(path: Path) -> dict[tuple[str, str, str], str]:
    data = read_json(path, "reader translation publication map")
    if set(data) != {"schema_version", "canonical_language", "translations"}:
        raise LocaleViewerError("reader translation publication map has unsupported fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise LocaleViewerError("reader translation publication map schema_version must be integer 1")
    if data["canonical_language"] != "en" or not isinstance(data["translations"], list):
        raise LocaleViewerError("reader translation publication map is invalid")
    result: dict[tuple[str, str, str], str] = {}
    for index, record in enumerate(data["translations"]):
        field = f"reader translation publication map translations[{index}]"
        if not isinstance(record, dict):
            raise LocaleViewerError(f"{field} must be an object")
        required = {
            "publication",
            "language",
            "canonical_destination",
            "translation_destination",
        }
        if set(record) != required:
            raise LocaleViewerError(f"{field} has unsupported fields")
        language = validate_language(record["language"], f"{field}.language")
        publication = record["publication"]
        if not isinstance(publication, str) or not publication:
            raise LocaleViewerError(f"{field}.publication must be a non-empty string")
        canonical = safe_markdown_destination(
            record["canonical_destination"],
            f"{field}.canonical_destination",
        )
        translation = safe_markdown_destination(
            record["translation_destination"],
            f"{field}.translation_destination",
        )
        expected_translation = PurePosixPath(language) / canonical
        if translation != expected_translation:
            raise LocaleViewerError(
                f"{field}.translation_destination must mirror canonical at "
                f"{expected_translation}"
            )
        key = (language, publication, canonical.as_posix())
        if key in result:
            raise LocaleViewerError("reader translation publication record is duplicate")
        result[key] = translation.as_posix()
    return result


def locale_index_url(language: str, provider: str, source_path: str, *, root_index: str = ROOT_INDEX) -> str:
    language = validate_language(language)
    return f"/{quote(language, safe='')}" + index_page_url(provider, source_path, root_index=root_index)


def locale_index_path(language: str, provider: str, source_path: str, *, root_index: str = ROOT_INDEX) -> Path:
    language = validate_language(language)
    return Path(language) / index_page_path(provider, source_path, root_index=root_index)


def translated_edge_href(
    language: str,
    repository: str,
    provider: dict[str, Any],
    edge: dict[str, Any],
    published: dict[str, str],
    overlay_indexes: dict[str, dict[str, Any]],
    reader_translations: dict[tuple[str, str, str], str],
) -> tuple[str, str, bool]:
    language = validate_language(language)
    kind = edge["kind"]
    target = edge["target"]
    fragment = edge.get("fragment")
    if kind == "index" and target in overlay_indexes:
        suffix = "" if fragment is None else "#" + quote(fragment, safe="-._~:/")
        return locale_index_url(language, provider["name"], target, root_index=provider.get("root_index", ROOT_INDEX)) + suffix, "index", False
    if kind == "fragment":
        suffix = "" if fragment is None else "#" + quote(fragment, safe="-._~:/")
        return suffix, "same index", False
    if kind == "file":
        canonical_destination = published.get(target)
        if canonical_destination is not None:
            translated_destination = reader_translations.get(
                (language, provider["name"], canonical_destination)
            )
            # Reader translations do not preserve canonical heading IDs. Route a
            # fragment-bearing edge to the canonical reader unless a fragment map
            # exists in a future contract; otherwise the localized anchor is unsafe.
            if translated_destination is not None and fragment is None:
                return (
                    public_path(translated_destination),
                    "published document",
                    False,
                )
    return edge_href(
        provider["name"],
        provider["revision"],
        edge,
        published,
        repository,
        root_index=provider.get("root_index", ROOT_INDEX),
    )


def localized_shell(title: str, body: str, page_path: str, language: str) -> str:
    language = validate_language(language)
    source = page_shell(title, body, page_path)
    source = source.replace('<html lang="en">', f'<html lang="{html.escape(language, quote=True)}">', 1)
    if is_japanese(language):
        source = source.replace("Page path:", JA_STRINGS["page_path"], 1)
    return source


def path_chain(
    current: str,
    parents: dict[str, tuple[str, str]],
    *, root_index: str = ROOT_INDEX,
) -> list[str]:
    chain = [current]
    seen = {current}
    while chain[-1] != root_index:
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
    origin = github_blob_url(
        repository,
        provider["revision"],
        edge["source"],
        fragment=f"L{edge['line']}",
    )
    ja = is_japanese(language)
    metadata = [
        f'<span class="badge">{html.escape(ROUTE_LABELS_JA.get(route_kind, route_kind) if ja else route_kind)}</span>',
        f'<a href="{html.escape(origin, quote=True)}" target="_blank" rel="noopener">{JA_STRINGS["index_line"] if ja else "index line"} {edge["line"]}</a>',
    ]
    if source is not None:
        label = JA_STRINGS["immutable_source_short"] if ja else "immutable source"
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
    language = validate_language(language)
    source_path = canonical_index["path"]
    source = github_blob_url(repository, provider["revision"], source_path)
    revision = github_commit_url(repository, provider["revision"])
    breadcrumbs = []
    for path in path_chain(source_path, parents, root_index=provider.get("root_index", ROOT_INDEX)):
        path_overlay = overlay_indexes.get(path)
        title = path_overlay["title"] if path_overlay is not None else indexes[path]["title"]
        url = (
            locale_index_url(language, provider["name"], path, root_index=provider.get("root_index", ROOT_INDEX))
            if path_overlay is not None
            else index_page_url(provider["name"], path, root_index=provider.get("root_index", ROOT_INDEX))
        )
        breadcrumbs.append((title, url))
    breadcrumb_html = "".join(
        f'<span><a href="{html.escape(url, quote=True)}">{html.escape(title)}</a></span>'
        for title, url in breadcrumbs
    )

    localized_sections = overlay["sections"]
    canonical_sections = canonical_index["sections"]
    canonical_section_titles = [_section_title(section) for section in canonical_sections]
    # Localized pages deliberately preserve the canonical English heading IDs. This
    # keeps canonical graph fragments valid while only the visible prose is localized.
    heading_ids = heading_anchors([canonical_index["title"], *canonical_section_titles])
    localized_links = overlay["links"]
    edge_pairs = list(zip(edges, localized_links, strict=True))
    unsectioned = [pair for pair in edge_pairs if pair[0].get("section") is None]
    by_section: dict[str, list[tuple[dict[str, Any], dict[str, str]]]] = {}
    for edge, localized in edge_pairs:
        if edge.get("section") is not None:
            by_section.setdefault(edge["section"], []).append((edge, localized))

    ja = is_japanese(language)
    strings = JA_STRINGS
    body_parts = [
        f'<p class="eyebrow">{html.escape(strings["eyebrow"] if ja else "Index-guided navigation")}</p>',
        f'<h1 id="{html.escape(heading_ids[0], quote=True)}">{html.escape(overlay["title"])}</h1>',
        f'<p class="notice">{html.escape(strings["notice"] if ja else "This localized view projects non-authoritative translated prose onto the canonical English navigation graph.")}</p>',
        f'<nav class="breadcrumbs" aria-label="Index path">{breadcrumb_html}</nav>',
        '<div class="meta">',
        f'<p><strong>{html.escape(strings["provider"] if ja else "Provider")}:</strong> <code>{html.escape(provider["name"])}</code></p>',
        f'<p><strong>{html.escape(strings["revision"] if ja else "Revision")}:</strong> <a href="{html.escape(revision, quote=True)}" target="_blank" rel="noopener"><code>{html.escape(provider["revision"])}</code></a></p>',
        f'<p><strong>{html.escape(strings["source"] if ja else "Source")}:</strong> <code>{html.escape(source_path)}</code> · <a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">{html.escape(strings["immutable_source"] if ja else "immutable GitHub source")}</a></p>',
        f'<p><strong>{html.escape(strings["repository"] if ja else "Repository")}:</strong> <a href="{html.escape(github_tree_url(repository, provider["revision"]), quote=True)}" target="_blank" rel="noopener">{html.escape(strings["browse_snapshot"] if ja else "open the same snapshot on GitHub")}</a></p>',
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
        locale_index_url(language, provider["name"], source_path, root_index=provider.get("root_index", ROOT_INDEX)),
        language,
    )


def render_localized_landing(
    language: str,
    graph: dict[str, Any],
    locale: dict[str, dict[str, dict[str, Any]]],
) -> str:
    language = validate_language(language)
    repository = graph.get("repository", "TakashiSasaki/templates")
    ja = is_japanese(language)
    strings = JA_STRINGS
    cards = []
    for provider in graph["providers"]:
        name = provider["name"]
        diagnostics = provider["diagnostics"]
        root_index = provider.get("root_index", ROOT_INDEX)
        root_overlay = locale.get(name, {}).get(root_index)
        target = (
            locale_index_url(language, name, root_index, root_index=root_index)
            if root_overlay is not None
            else index_page_url(name, root_index, root_index=root_index)
        )
        cards.append(
            '<section class="provider-card">'
            f'<h2><a href="{html.escape(target, quote=True)}">{html.escape(name)}</a></h2>'
            f'<p><a href="{html.escape(github_commit_url(repository, provider["revision"]), quote=True)}" target="_blank" rel="noopener"><code>{html.escape(provider["revision"])}</code></a></p>'
            f'<p>{diagnostics["index_count"]} {html.escape(strings["reachable"] if ja else "reachable indexes")} · '
            f'{diagnostics["edge_count"]} {html.escape(strings["links"] if ja else "links")} · '
            f'{html.escape(strings["depth"] if ja else "maximum index depth")} {diagnostics["max_index_depth"]}</p>'
            f'<p><a href="{html.escape(github_tree_url(repository, provider["revision"]), quote=True)}" target="_blank" rel="noopener">{html.escape(strings["browse_same"] if ja else "Open the same repository snapshot on GitHub")}</a></p>'
            "</section>"
        )
    body = "\n".join(
        [
            f'<p class="eyebrow">{html.escape(strings["human_agent"] if ja else "Human / agent shared path")}</p>',
            f'<h1>{html.escape(strings["landing_title"] if ja else "Index-guided document discovery")}</h1>',
            f'<p class="notice">{html.escape(strings["landing_notice"] if ja else "This localized view follows the canonical provider-owned index navigation graph.")}</p>',
            f'<p><a href="/guided/graph.json">{html.escape(strings["inspect_graph"] if ja else "Inspect the machine-readable navigation graph")}</a></p>',
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
    parent = existing_directory_without_symlinks(
        path.parent,
        "guided locale publication map parent",
    )
    target = parent / path.name
    if target.exists() or target.is_symlink():
        raise LocaleViewerError(
            f"guided locale publication map destination already exists: {target}"
        )
    target.write_text(
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



def generate_from_bundle(repository, graph, overlays, reader_translations, published, output_root, pair_map):
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
        for name in providers_by_name:
            provider_overlays = locale.get(name, {})
            if not provider_overlays:
                continue
            provider = providers_by_name[name]
            indexes, parents, edges_by_source = provider_render_indexes(provider)
            for source_path, overlay in provider_overlays.items():
                canonical_index = indexes[source_path]
                relative = locale_index_path(language, name, source_path, root_index=provider["root_index"])
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
                        "canonical_path": index_page_path(name, source_path, root_index=provider["root_index"]).as_posix(),
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
