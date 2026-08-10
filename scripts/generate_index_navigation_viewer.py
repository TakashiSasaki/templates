#!/usr/bin/env python3
"""Render the immutable provider index navigation graph as static HTML."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

try:
    from scripts.generate_index_navigation import (
        PROVIDER_ORDER,
        ROOT_INDEX,
        IndexNavigationError,
        parse_providers,
    )
    from scripts.generate_repository_browser import viewer_relative_url
    from scripts.generate_repository_trees import (
        REPOSITORY,
        checked_revision,
        github_url,
        published_sources,
        published_url,
    )
except ModuleNotFoundError:
    from generate_index_navigation import (
        PROVIDER_ORDER,
        ROOT_INDEX,
        IndexNavigationError,
        parse_providers,
    )
    from generate_repository_browser import viewer_relative_url
    from generate_repository_trees import (
        REPOSITORY,
        checked_revision,
        github_url,
        published_sources,
        published_url,
    )


GUIDED_ROOT = Path("guided")
MARKER = ".index-navigation-root"
MARKER_CONTENT = "managed by scripts/generate_index_navigation_viewer.py\n"
LINE_FRAGMENT = re.compile(r"L[1-9][0-9]*")


class IndexNavigationViewerError(RuntimeError):
    """Raised when a guided-navigation viewer cannot be rendered safely."""


def load_graph(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise IndexNavigationViewerError(f"graph must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndexNavigationViewerError(f"unable to read index graph {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise IndexNavigationViewerError("index graph must use schema_version 1")
    repository = value.get("repository")
    providers = value.get("providers")
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise IndexNavigationViewerError("index graph repository is invalid")
    if not isinstance(providers, list):
        raise IndexNavigationViewerError("index graph providers must be an array")
    names = [provider.get("name") if isinstance(provider, dict) else None for provider in providers]
    if names != list(PROVIDER_ORDER):
        raise IndexNavigationViewerError(
            "index graph providers must be ordered exactly as: " + ", ".join(PROVIDER_ORDER)
        )
    return value


def validate_provider_graph(provider: dict[str, Any]) -> None:
    name = provider.get("name")
    revision = provider.get("revision")
    root_index = provider.get("root_index")
    indexes = provider.get("indexes")
    edges = provider.get("edges")
    diagnostics = provider.get("diagnostics")
    if not isinstance(name, str) or name not in PROVIDER_ORDER:
        raise IndexNavigationViewerError("provider name is invalid")
    if not isinstance(revision, str) or len(revision) != 40:
        raise IndexNavigationViewerError(f"{name} revision is invalid")
    if root_index != ROOT_INDEX:
        raise IndexNavigationViewerError(f"{name} root index is invalid")
    if not isinstance(indexes, list) or not indexes:
        raise IndexNavigationViewerError(f"{name} indexes must be a non-empty array")
    if not isinstance(edges, list) or not isinstance(diagnostics, dict):
        raise IndexNavigationViewerError(f"{name} graph shape is invalid")

    paths: set[str] = set()
    for index in indexes:
        if not isinstance(index, dict):
            raise IndexNavigationViewerError(f"{name} index record must be an object")
        path = index.get("path")
        title = index.get("title")
        sections = index.get("sections")
        depth = index.get("depth")
        object_id = index.get("object_id")
        if (
            not isinstance(path, str)
            or not path.endswith("/index.md")
            or not isinstance(title, str)
            or not isinstance(sections, list)
            or not all(isinstance(section, str) for section in sections)
            or not isinstance(depth, int)
            or depth < 0
            or not isinstance(object_id, str)
            or len(object_id) != 40
        ):
            raise IndexNavigationViewerError(f"{name} index record is invalid")
        if len(set(sections)) != len(sections):
            raise IndexNavigationViewerError(
                f"{name} index contains duplicate section headings: {path}"
            )
        if path in paths:
            raise IndexNavigationViewerError(f"{name} graph contains duplicate index path: {path}")
        paths.add(path)
    if ROOT_INDEX not in paths:
        raise IndexNavigationViewerError(f"{name} graph does not contain its root index")

    allowed_kinds = {"index", "file", "directory", "fragment", "external"}
    for edge in edges:
        if not isinstance(edge, dict):
            raise IndexNavigationViewerError(f"{name} edge must be an object")
        if edge.get("source") not in paths:
            raise IndexNavigationViewerError(f"{name} edge source is not a rendered index")
        if edge.get("kind") not in allowed_kinds:
            raise IndexNavigationViewerError(f"{name} edge kind is invalid")
        if not all(
            isinstance(edge.get(field), str)
            for field in ("label", "description", "raw_target", "target")
        ):
            raise IndexNavigationViewerError(f"{name} edge text fields are invalid")
        if not isinstance(edge.get("line"), int) or edge["line"] < 1:
            raise IndexNavigationViewerError(f"{name} edge line is invalid")
        section = edge.get("section")
        fragment = edge.get("fragment")
        if section is not None and not isinstance(section, str):
            raise IndexNavigationViewerError(f"{name} edge section is invalid")
        if section is not None:
            source_index = next(index for index in indexes if index["path"] == edge["source"])
            if section not in source_index["sections"]:
                raise IndexNavigationViewerError(f"{name} edge section is not declared by its index")
        if fragment is not None and not isinstance(fragment, str):
            raise IndexNavigationViewerError(f"{name} edge fragment is invalid")
        if edge["kind"] == "index" and edge["target"] not in paths:
            raise IndexNavigationViewerError(
                f"{name} index edge targets a non-rendered index: {edge['target']}"
            )


def prepare_guided_root(output_root: Path) -> Path:
    if output_root.is_symlink() or not output_root.is_dir():
        raise IndexNavigationViewerError("output root must be an existing directory")
    guided = output_root / GUIDED_ROOT
    if guided.exists() or guided.is_symlink():
        raise IndexNavigationViewerError(
            "guided-navigation destination already exists; refusing to overwrite"
        )
    guided.mkdir()
    (guided / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
    return guided


def encoded_path(parts: tuple[str, ...]) -> str:
    return "/".join(quote(part, safe="") for part in parts)


def index_page_path(provider: str, source_path: str) -> Path:
    if source_path == ROOT_INDEX:
        return GUIDED_ROOT / provider / "index.html"
    parent = PurePosixPath(source_path).parent
    if source_path != f"{parent.as_posix()}/index.md":
        raise IndexNavigationViewerError(f"not an index source path: {source_path}")
    return GUIDED_ROOT / provider / Path(parent.as_posix()) / "index.html"


def index_page_url(provider: str, source_path: str) -> str:
    if source_path == ROOT_INDEX:
        return f"/guided/{quote(provider, safe='')}/"
    parent = PurePosixPath(source_path).parent
    suffix = encoded_path(tuple(parent.parts))
    return f"/guided/{quote(provider, safe='')}/{suffix}/"


def fragment_suffix(fragment: str | None) -> str:
    return "" if fragment is None else "#" + quote(fragment, safe="-._~:/")


def heading_anchor(value: str) -> str:
    """Return the deterministic anchor used by guided pages for provider headings."""
    anchor = value.strip().casefold()
    anchor = re.sub(r"[^\w\s-]", "", anchor, flags=re.UNICODE)
    anchor = re.sub(r"\s+", "-", anchor, flags=re.UNICODE).strip("-")
    if not anchor:
        raise IndexNavigationViewerError(f"heading cannot produce a stable anchor: {value!r}")
    return anchor


def heading_anchors(values: list[str]) -> list[str]:
    """Return stable unique anchors while preserving heading order."""
    anchors: list[str] = []
    used: set[str] = set()
    for value in values:
        base = heading_anchor(value)
        candidate = base
        suffix = 1
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate)
        anchors.append(candidate)
    return anchors


def published_maps(
    site_root: Path,
    provider_roots: dict[str, Path],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for provider in PROVIDER_ORDER:
        try:
            mapping = published_sources(provider, provider_roots[provider], site_root)
        except Exception as exc:
            raise IndexNavigationViewerError(
                f"unable to resolve published sources for {provider}: {exc}"
            ) from exc
        decoded: dict[str, str] = {}
        for source, destination in mapping.items():
            try:
                path = source.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise IndexNavigationViewerError(
                    f"{provider} publication catalog contains a non-UTF-8 source path"
                ) from exc
            decoded[path] = destination
        result[provider] = decoded
    return result


def edge_href(
    provider: str,
    revision: str,
    edge: dict[str, Any],
    published: dict[str, str],
    repository: str | None = None,
) -> tuple[str, str, bool]:
    kind = edge["kind"]
    target = edge["target"]
    fragment = edge.get("fragment")
    if kind == "index":
        return index_page_url(provider, target) + fragment_suffix(fragment), "index", False
    if kind == "fragment":
        return fragment_suffix(fragment), "same index", False
    if kind == "external":
        return target + fragment_suffix(fragment), "external", True
    if kind == "directory":
        return f"/files/{quote(provider, safe='')}/", "repository directory", False
    if kind == "file":
        destination = published.get(target)
        if destination is not None:
            return (
                published_url("/", destination) + fragment_suffix(fragment),
                "published document",
                False,
            )
        if fragment is not None and LINE_FRAGMENT.fullmatch(fragment) is None:
            if repository is None:
                raise IndexNavigationViewerError(
                    "repository is required for a semantic source-file fragment"
                )
            source = github_url(repository, revision, "blob", target.encode("utf-8"))
            return source + fragment_suffix(fragment), "immutable source", True
        relative = viewer_relative_url(provider, revision, target.encode("utf-8"))
        return (
            f"/files/{quote(provider, safe='')}/{relative}" + fragment_suffix(fragment),
            "source file",
            False,
        )
    raise IndexNavigationViewerError(f"unsupported edge kind: {kind}")


def immutable_target_url(repository: str, revision: str, edge: dict[str, Any]) -> str | None:
    kind = edge["kind"]
    if kind == "external":
        return None
    target = edge["target"]
    if kind == "fragment":
        target = edge["source"]
        git_kind = "blob"
    elif kind == "directory":
        git_kind = "tree"
    else:
        git_kind = "blob"
    return github_url(repository, revision, git_kind, target.encode("utf-8"))


def canonical_parent_map(provider: dict[str, Any]) -> dict[str, tuple[str, str]]:
    depths = {index["path"]: index["depth"] for index in provider["indexes"]}
    parents: dict[str, tuple[str, str]] = {}
    for edge in provider["edges"]:
        if edge["kind"] != "index":
            continue
        source = edge["source"]
        target = edge["target"]
        if target in parents:
            continue
        if depths.get(target) == depths.get(source, -1) + 1:
            parents[target] = (source, edge["label"])
    return parents


def breadcrumb_chain(provider: dict[str, Any], current: str) -> list[tuple[str, str]]:
    indexes = {index["path"]: index for index in provider["indexes"]}
    parents = canonical_parent_map(provider)
    chain: list[str] = [current]
    seen = {current}
    while chain[-1] != ROOT_INDEX:
        parent = parents.get(chain[-1])
        if parent is None:
            break
        path = parent[0]
        if path in seen:
            break
        seen.add(path)
        chain.append(path)
    chain.reverse()
    return [
        (indexes[path]["title"], index_page_url(provider["name"], path))
        for path in chain
    ]


def page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; manifest-src 'self'; base-uri 'none'; form-action 'none'">
<title>{html.escape(title)} · templates guided navigation</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: Canvas; color: CanvasText; }}
main {{ max-width: 74rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
a {{ color: LinkText; }}
code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }}
.eyebrow {{ font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; opacity: .65; }}
.meta {{ padding: .8rem 1rem; border: 1px solid color-mix(in srgb, CanvasText 18%, transparent); border-radius: .6rem; background: color-mix(in srgb, CanvasText 3%, Canvas); }}
.meta p {{ margin: .25rem 0; }}
.breadcrumbs {{ display: flex; flex-wrap: wrap; gap: .35rem; margin: 1rem 0; font-size: .9rem; }}
.breadcrumbs span::after {{ content: '›'; margin-left: .35rem; opacity: .45; }}
.breadcrumbs span:last-child::after {{ content: ''; margin: 0; }}
.section {{ margin-top: 2rem; }}
.link-list {{ list-style: none; padding: 0; display: grid; gap: .7rem; }}
.link-card {{ border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: .65rem; padding: .85rem 1rem; }}
.link-card p {{ margin: .35rem 0 0; line-height: 1.45; }}
.link-meta {{ display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .45rem; font-size: .76rem; opacity: .72; }}
.badge {{ border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); border-radius: 999px; padding: .08rem .45rem; }}
.provider-grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(15rem,1fr)); gap: 1rem; margin-top: 1.5rem; }}
.provider-card {{ border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: .7rem; padding: 1rem; }}
.provider-card h2 {{ margin-top: 0; }}
.notice {{ border-left: .25rem solid color-mix(in srgb, CanvasText 35%, transparent); padding-left: .9rem; }}
</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def render_edge(
    repository: str,
    provider: dict[str, Any],
    edge: dict[str, Any],
    published: dict[str, str],
) -> str:
    href, route_kind, external = edge_href(
        provider["name"], provider["revision"], edge, published, repository
    )
    source = immutable_target_url(repository, provider["revision"], edge)
    attrs = ' target="_blank" rel="noopener"' if external else ""
    source_link = ""
    if source is not None:
        source_link = (
            f'<a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">'
            "immutable source</a>"
        )
    origin = github_url(
        repository,
        provider["revision"],
        "blob",
        edge["source"].encode("utf-8"),
    ) + f"#L{edge['line']}"
    metadata = [
        f'<span class="badge">{html.escape(route_kind)}</span>',
        f'<a href="{html.escape(origin, quote=True)}" target="_blank" rel="noopener">index line {edge["line"]}</a>',
    ]
    if source_link:
        metadata.append(source_link)
    return (
        '<li class="link-card">'
        f'<a href="{html.escape(href, quote=True)}"{attrs}><strong>{html.escape(edge["label"])}</strong></a>'
        f'<p>{html.escape(edge["description"])}</p>'
        f'<div class="link-meta">{" · ".join(metadata)}</div>'
        "</li>"
    )


def render_index_page(
    repository: str,
    provider: dict[str, Any],
    index: dict[str, Any],
    published: dict[str, str],
) -> str:
    source_path = index["path"]
    source = github_url(
        repository,
        provider["revision"],
        "blob",
        source_path.encode("utf-8"),
    )
    breadcrumbs = breadcrumb_chain(provider, source_path)
    breadcrumb_html = "".join(
        f'<span><a href="{html.escape(url, quote=True)}">{html.escape(title)}</a></span>'
        for title, url in breadcrumbs
    )
    heading_ids = heading_anchors([index["title"], *index["sections"]])
    edges = [edge for edge in provider["edges"] if edge["source"] == source_path]
    body_parts = [
        '<p class="eyebrow">Index-guided navigation</p>',
        f'<h1 id="{html.escape(heading_ids[0], quote=True)}">{html.escape(index["title"])}</h1>',
        '<p class="notice">This view projects the provider-owned <code>index.md</code> navigation at the exact locked revision. Link order, labels, descriptions, and sections come from the navigation graph rather than a separate Site information architecture.</p>',
        f'<nav class="breadcrumbs" aria-label="Index path">{breadcrumb_html}</nav>',
        '<div class="meta">',
        f'<p><strong>Provider:</strong> <code>{html.escape(provider["name"])}</code></p>',
        f'<p><strong>Revision:</strong> <code>{html.escape(provider["revision"])}</code></p>',
        f'<p><strong>Source:</strong> <code>{html.escape(source_path)}</code> · <a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">immutable GitHub source</a></p>',
        f'<p><strong>Repository:</strong> <a href="/files/{quote(provider["name"], safe="")}/">browse the same snapshot</a></p>',
        "</div>",
    ]

    unsectioned = [edge for edge in edges if edge.get("section") is None]
    if unsectioned:
        body_parts.append(
            '<div class="section" aria-label="Links before the first provider section">'
            '<p class="eyebrow">Links before the first provider section</p>'
            '<ul class="link-list">'
        )
        body_parts.extend(
            render_edge(repository, provider, edge, published) for edge in unsectioned
        )
        body_parts.append("</ul></div>")

    for section_number, section in enumerate(index["sections"], start=1):
        section_edges = [edge for edge in edges if edge.get("section") == section]
        anchor = heading_ids[section_number]
        body_parts.append(
            f'<section class="section"><h2 id="{html.escape(anchor, quote=True)}">{html.escape(section)}</h2>'
        )
        if section_edges:
            body_parts.append('<ul class="link-list">')
            body_parts.extend(
                render_edge(repository, provider, edge, published) for edge in section_edges
            )
            body_parts.append("</ul>")
        else:
            body_parts.append("<p><em>No links in this section.</em></p>")
        body_parts.append("</section>")

    return page_shell(index["title"], "\n".join(body_parts))


def render_landing(graph: dict[str, Any]) -> str:
    cards = []
    for provider in graph["providers"]:
        diagnostics = provider["diagnostics"]
        cards.append(
            '<section class="provider-card">'
            f'<h2><a href="/guided/{quote(provider["name"], safe="")}/">{html.escape(provider["name"])}</a></h2>'
            f'<p><code>{html.escape(provider["revision"])}</code></p>'
            f'<p>{diagnostics.get("index_count", 0)} reachable indexes · '
            f'{diagnostics.get("edge_count", 0)} links · '
            f'maximum index depth {diagnostics.get("max_index_depth", 0)}</p>'
            f'<p><a href="/files/{quote(provider["name"], safe="")}/">Browse the same repository snapshot</a></p>'
            "</section>"
        )
    body = "\n".join(
        [
            '<p class="eyebrow">Human / agent shared path</p>',
            "<h1>Index-guided document discovery</h1>",
            '<p class="notice">Follow the same provider-owned <code>index.md</code> structure that an AI agent can use before falling back to search. This surface is generated from immutable provider revisions and is separate from the Site-authored reader navigation.</p>',
            '<p><a href="/guided/graph.json">Inspect the machine-readable navigation graph</a> · <a href="/files/">Browse all source snapshots</a></p>',
            f'<div class="provider-grid">{"".join(cards)}</div>',
        ]
    )
    return page_shell("Index-guided document discovery", body)


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

    for provider in graph["providers"]:
        validate_provider_graph(provider)
        actual = checked_revision(provider_roots[provider["name"]])
        if actual != provider["revision"]:
            raise IndexNavigationViewerError(
                f"{provider['name']} graph revision {provider['revision']} does not match checkout {actual}"
            )

    published = published_maps(site_root, provider_roots)
    guided = prepare_guided_root(output_root)
    (guided / "graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (guided / "index.html").write_text(render_landing(graph), encoding="utf-8")

    messages: list[str] = []
    for provider in graph["providers"]:
        name = provider["name"]
        for index in provider["indexes"]:
            destination = output_root / index_page_path(name, index["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                render_index_page(repository, provider, index, published[name]),
                encoding="utf-8",
            )
        messages.append(
            f"generated guided navigation for {name} @ {provider['revision']} "
            f"({len(provider['indexes'])} index pages)"
        )
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
    except (IndexNavigationError, IndexNavigationViewerError) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
