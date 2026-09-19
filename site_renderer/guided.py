"""Render a validated canonical navigation graph and destination read model."""
from __future__ import annotations
import html
import json
import re
import shutil
import unicodedata
import copy
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit
from publication_bundle.graph import *
from publication_bundle.graph import _section_title, _section_level
from publication_bundle.paths import public_path
from site_renderer.github import (
    github_blob_url,
    github_commit_url,
    github_tree_url,
    immutable_github_source_url,
)

GUIDED_ROOT = Path("guided")


ROOT_INDEX_NAMESPACE = "_repository-root"


MARKER = ".index-navigation-root"


MARKER_CONTENT = "managed by scripts/generate_index_navigation_viewer.py\n"


IDCOUNT_RE = re.compile(r"^(.*)_([0-9]+)$")


def prepare_guided_root(output_root: Path) -> Path:
    if output_root.is_symlink() or not output_root.is_dir():
        raise IndexNavigationViewerError("output root must be an existing directory")
    guided = output_root / GUIDED_ROOT
    if guided.exists() or guided.is_symlink():
        raise IndexNavigationViewerError(
            "guided-navigation destination already exists; refusing to overwrite"
        )
    guided.mkdir()
    try:
        (guided / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
    except BaseException:
        shutil.rmtree(guided, ignore_errors=True)
        raise
    return guided


def encoded_path(parts: tuple[str, ...]) -> str:
    return "/".join(quote(part, safe="") for part in parts)


def index_page_path(provider: str, source_path: str, *, root_index: str = ROOT_INDEX) -> Path:
    validate_repository_path(source_path, "index source path")
    if not is_index_source_path(source_path):
        raise IndexNavigationViewerError(f"not an index source path: {source_path}")
    if source_path == root_index:
        return GUIDED_ROOT / provider / "index.html"
    if source_path == ROOT_INDEX:
        return GUIDED_ROOT / ROOT_INDEX_NAMESPACE / provider / "index.html"
    parent = PurePosixPath(source_path).parent
    return GUIDED_ROOT / provider / Path(parent.as_posix()) / "index.html"


def index_page_url(provider: str, source_path: str, *, root_index: str = ROOT_INDEX) -> str:
    validate_repository_path(source_path, "index source path")
    if not is_index_source_path(source_path):
        raise IndexNavigationViewerError(f"not an index source path: {source_path}")
    if source_path == root_index:
        return f"/guided/{quote(provider, safe='')}/"
    if source_path == ROOT_INDEX:
        return f"/guided/{ROOT_INDEX_NAMESPACE}/{quote(provider, safe='')}/"
    parent = PurePosixPath(source_path).parent
    suffix = encoded_path(tuple(parent.parts))
    return f"/guided/{quote(provider, safe='')}/{suffix}/"


def fragment_suffix(fragment: str | None) -> str:
    return "" if fragment is None else "#" + quote(fragment, safe="-._~:/")


def heading_anchor(value: str) -> str:
    anchor = unicodedata.normalize("NFC", value).strip().lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor, flags=re.UNICODE)
    anchor = re.sub(r"[-\s]+", "-", anchor, flags=re.UNICODE).strip("-")
    if not anchor:
        raise IndexNavigationViewerError(
            f"heading cannot produce a stable anchor: {value!r}"
        )
    return anchor


def heading_anchors(values: list[str]) -> list[str]:
    anchors: list[str] = []
    used: set[str] = set()
    next_suffix: dict[str, int] = {}
    for value in values:
        candidate = heading_anchor(value)
        if candidate in used:
            match = IDCOUNT_RE.match(candidate)
            if match:
                root = match.group(1)
                suffix = max(
                    int(match.group(2)) + 1,
                    next_suffix.get(root, int(match.group(2)) + 1),
                )
            else:
                root = candidate
                suffix = next_suffix.get(root, 1)
            candidate = f"{root}_{suffix}"
            while candidate in used:
                suffix += 1
                candidate = f"{root}_{suffix}"
            next_suffix[root] = suffix + 1
        used.add(candidate)
        if IDCOUNT_RE.match(candidate) is None:
            next_suffix.setdefault(candidate, 1)
        anchors.append(candidate)
    return anchors


def immutable_edge_path(kind: str, target: str) -> bytes:
    if kind == "directory" and target == ".":
        return b""
    return target.encode("utf-8")


def edge_href(
    provider: str,
    revision: str,
    edge: dict[str, Any],
    published: dict[str, str],
    repository: str | None = None,
    *, root_index: str = ROOT_INDEX,
) -> tuple[str, str, bool]:
    kind = edge["kind"]
    target = edge["target"]
    fragment = edge.get("fragment")
    if kind == "index":
        return (
            index_page_url(provider, target, root_index=root_index) + fragment_suffix(fragment),
            "index",
            False,
        )
    if kind == "fragment":
        return fragment_suffix(fragment), "same index", False
    if kind == "external":
        target = immutable_github_source_url(
            target,
            {provider: revision},
            repository=repository or "TakashiSasaki/templates",
        )
        return target + fragment_suffix(fragment), "external", True
    if kind == "directory":
        if fragment is None:
            if repository is None:
                raise IndexNavigationViewerError(
                    "repository is required for a directory"
                )
            return (
                github_tree_url(repository, revision, immutable_edge_path(kind, target)),
                "immutable directory",
                True,
            )
        if repository is None:
            raise IndexNavigationViewerError(
                "repository is required for a directory fragment"
            )
        return (
            github_tree_url(
                repository,
                revision,
                immutable_edge_path(kind, target),
                fragment=fragment,
            ),
            "immutable directory",
            True,
        )
    if kind == "file":
        destination = published.get(target)
        if destination is not None:
            return (
                public_path(destination) + fragment_suffix(fragment),
                "published document",
                False,
            )
        if fragment is not None:
            if repository is None:
                raise IndexNavigationViewerError(
                    "repository is required for a source-file fragment"
                )
            source = github_blob_url(
                repository, revision, target, fragment=fragment
            )
            return source, "immutable source", True
        return (
            github_blob_url(repository, revision, target),
            "immutable source",
            True,
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
    if git_kind == "tree":
        return github_tree_url(repository, revision, immutable_edge_path(kind, target))
    return github_blob_url(repository, revision, immutable_edge_path(kind, target))


def provider_render_indexes(
    provider: dict[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, tuple[str, str]],
    dict[str, list[dict[str, Any]]],
]:
    indexes = {index["path"]: index for index in provider["indexes"]}
    depths = {path: index["depth"] for path, index in indexes.items()}
    parents: dict[str, tuple[str, str]] = {}
    edges_by_source: dict[str, list[dict[str, Any]]] = {
        path: [] for path in indexes
    }
    for edge in provider["edges"]:
        source = edge["source"]
        edges_by_source[source].append(edge)
        if edge["kind"] != "index":
            continue
        target = edge["target"]
        if target in parents:
            continue
        if depths.get(target) == depths.get(source, -1) + 1:
            parents[target] = (source, edge["label"])
    return indexes, parents, edges_by_source


def canonical_parent_map(provider: dict[str, Any]) -> dict[str, tuple[str, str]]:
    _indexes, parents, _edges_by_source = provider_render_indexes(provider)
    return parents


def breadcrumb_chain(
    provider: dict[str, Any],
    current: str,
    indexes: dict[str, dict[str, Any]] | None = None,
    parents: dict[str, tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    if indexes is None or parents is None:
        built_indexes, built_parents, _edges_by_source = provider_render_indexes(provider)
        if indexes is None:
            indexes = built_indexes
        if parents is None:
            parents = built_parents
    chain: list[str] = [current]
    seen = {current}
    while chain[-1] != provider.get("root_index", ROOT_INDEX):
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
        (indexes[path]["title"], index_page_url(provider["name"], path, root_index=provider.get("root_index", ROOT_INDEX)))
        for path in chain
    ]


def page_shell(title: str, body: str, page_path: str | None = None) -> str:
    path_html = ""
    if page_path is not None:
        path_html = (
            '<p class="page-path"><span class="page-path-label">Page path:</span> '
            f'<code>{html.escape(page_path)}</code></p>\n'
        )
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
.page-path {{ margin: 0 0 1rem; padding: .5rem .7rem; border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: .55rem; background: color-mix(in srgb, CanvasText 3%, Canvas); font-size: .86rem; }}
.page-path-label {{ font-weight: 650; margin-right: .25rem; }}
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
{path_html}{body}
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
        provider["name"], provider["revision"], edge, published, repository,
        root_index=provider.get("root_index", ROOT_INDEX),
    )
    source = immutable_target_url(repository, provider["revision"], edge)
    attrs = ' target="_blank" rel="noopener"' if external else ""
    source_link = ""
    if source is not None:
        source_link = (
            f'<a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">'
            "immutable source</a>"
        )
    origin = github_blob_url(
        repository,
        provider["revision"],
        edge["source"],
        fragment=f"L{edge['line']}",
    )
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
    edges: list[dict[str, Any]] | None = None,
    indexes: dict[str, dict[str, Any]] | None = None,
    parents: dict[str, tuple[str, str]] | None = None,
) -> str:
    source_path = index["path"]
    source = github_blob_url(repository, provider["revision"], source_path)
    revision = github_commit_url(repository, provider["revision"])
    breadcrumbs = breadcrumb_chain(provider, source_path, indexes, parents)
    breadcrumb_html = "".join(
        f'<span><a href="{html.escape(url, quote=True)}">{html.escape(title)}</a></span>'
        for title, url in breadcrumbs
    )
    section_titles = [_section_title(section) for section in index["sections"]]
    heading_ids = heading_anchors([index["title"], *section_titles])
    if edges is None:
        edges = [edge for edge in provider["edges"] if edge["source"] == source_path]

    unsectioned: list[dict[str, Any]] = []
    edges_by_section: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        edge_section = edge.get("section")
        if edge_section is None:
            unsectioned.append(edge)
        else:
            edges_by_section.setdefault(edge_section, []).append(edge)

    body_parts = [
        '<p class="eyebrow">Index-guided navigation</p>',
        f'<h1 id="{html.escape(heading_ids[0], quote=True)}">{html.escape(index["title"])}</h1>',
        '<p class="notice">This view projects the provider-owned <code>index.md</code> navigation at the exact locked revision. Link order, labels, descriptions, sections, and heading levels come from the navigation graph rather than a separate Site information architecture.</p>',
        f'<nav class="breadcrumbs" aria-label="Index path">{breadcrumb_html}</nav>',
        '<div class="meta">',
        f'<p><strong>Provider:</strong> <code>{html.escape(provider["name"])}</code></p>',
        f'<p><strong>Revision:</strong> <a href="{html.escape(revision, quote=True)}" target="_blank" rel="noopener"><code>{html.escape(provider["revision"])}</code></a></p>',
        f'<p><strong>Source:</strong> <code>{html.escape(source_path)}</code> · <a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">immutable GitHub source</a></p>',
        f'<p><strong>Repository:</strong> <a href="{html.escape(github_tree_url(repository, provider["revision"]), quote=True)}" target="_blank" rel="noopener">open the same snapshot on GitHub</a></p>',
        "</div>",
    ]

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
        title = _section_title(section)
        level = _section_level(section)
        section_edges = edges_by_section.get(title, [])
        anchor = heading_ids[section_number]
        body_parts.append(
            f'<section class="section"><h{level} id="{html.escape(anchor, quote=True)}">{html.escape(title)}</h{level}>'
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

    return page_shell(
        index["title"],
        "\n".join(body_parts),
        index_page_url(provider["name"], source_path, root_index=provider.get("root_index", ROOT_INDEX)),
    )


def render_landing(graph: dict[str, Any]) -> str:
    cards = []
    for provider in graph["providers"]:
        diagnostics = provider["diagnostics"]
        index_count = html.escape(str(diagnostics.get("index_count", 0)))
        edge_count = html.escape(str(diagnostics.get("edge_count", 0)))
        max_depth = html.escape(str(diagnostics.get("max_index_depth", 0)))
        cards.append(
            '<section class="provider-card">'
            f'<h2><a href="/guided/{quote(provider["name"], safe="")}/">{html.escape(provider["name"])}</a></h2>'
            f'<p><a href="{html.escape(github_commit_url(graph["repository"], provider["revision"]), quote=True)}" target="_blank" rel="noopener"><code>{html.escape(provider["revision"])}</code></a></p>'
            f'<p>{index_count} reachable indexes · '
            f'{edge_count} links · '
            f'maximum index depth {max_depth}</p>'
            f'<p><a href="{html.escape(github_tree_url(graph["repository"], provider["revision"]), quote=True)}" target="_blank" rel="noopener">Open the same repository snapshot on GitHub</a></p>'
            "</section>"
        )
    body = "\n".join(
        [
            '<p class="eyebrow">Human / agent shared path</p>',
            "<h1>Index-guided document discovery</h1>",
            '<p class="notice">Follow the same provider-owned <code>index.md</code> structure that an AI agent can use before falling back to search. This surface is generated from immutable provider revisions and is separate from the Site-authored reader navigation.</p>',
            '<p><a href="/guided/graph.json">Inspect the machine-readable navigation graph</a></p>',
            f'<div class="provider-grid">{"".join(cards)}</div>',
        ]
    )
    return page_shell("Index-guided document discovery", body, "/guided/")


def project_immutable_source_links(
    graph: dict[str, Any],
    *,
    revisions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Project provider-source URLs in the public graph onto exact revisions.

    The Bundle graph keeps the provider's semantic target as supplied by
    Integration. The Site's public graph is a rendered projection, so known
    GitHub blob/tree branch refs are replaced there without changing graph
    routing fields such as the file path used for publication resolution.
    """
    projected = copy.deepcopy(graph)
    known = dict(revisions or {})
    known.update(
        {
            provider["name"]: provider["revision"]
            for provider in projected.get("providers", [])
        }
    )
    repository = projected.get("repository", "TakashiSasaki/templates")
    for provider in projected.get("providers", []):
        for edge in provider.get("edges", []):
            if edge.get("kind") != "external":
                continue
            for field in ("raw_target", "target"):
                value = edge.get(field)
                if isinstance(value, str):
                    edge[field] = immutable_github_source_url(
                        value, known, repository=repository
                    )
    return projected


def validate_render_destinations(destinations: list[Path]) -> None:
    ordered = sorted(
        ((destination.parts, destination) for destination in destinations),
        key=lambda item: item[0],
    )
    previous_parts: tuple[str, ...] | None = None
    previous_destination: Path | None = None
    for parts, destination in ordered:
        if previous_parts == parts:
            raise IndexNavigationViewerError(
                f"duplicate guided-navigation destination: {destination}"
            )
        if (
            previous_parts is not None
            and len(previous_parts) < len(parts)
            and parts[: len(previous_parts)] == previous_parts
        ):
            raise IndexNavigationViewerError(
                "guided-navigation destinations have a file/directory collision: "
                f"{previous_destination} and {destination}"
            )
        previous_parts = parts
        previous_destination = destination



def generate_from_bundle(repository, graph, published, output_root):
    graph = project_immutable_source_links(graph)
    landing = render_landing(graph)
    rendered: list[tuple[Path, str]] = []
    messages: list[str] = []
    for provider in graph["providers"]:
        name = provider["name"]
        indexes, parents, edges_by_source = provider_render_indexes(provider)
        for index in provider["indexes"]:
            source_path = index["path"]
            relative = index_page_path(name, source_path, root_index=provider["root_index"])
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
