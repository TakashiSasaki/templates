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


GUIDED_ROOT = Path("guided")
ROOT_INDEX_NAMESPACE = "_repository-root"
MARKER = ".index-navigation-root"
MARKER_CONTENT = "managed by scripts/generate_index_navigation_viewer.py\n"
IDCOUNT_RE = re.compile(r"^(.*)_([0-9]+)$")


class IndexNavigationViewerError(RuntimeError):
    """Raised when a guided-navigation viewer cannot be rendered safely."""


def contains_non_scalar(value: str) -> bool:
    """Return whether a Python string contains a Unicode surrogate code point."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def load_graph(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise IndexNavigationViewerError(f"graph must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndexNavigationViewerError(f"unable to read index graph {path}: {exc}") from exc
    schema_version = value.get("schema_version") if isinstance(value, dict) else None
    if type(schema_version) is not int or schema_version != 1:
        raise IndexNavigationViewerError("index graph must use schema_version 1")
    repository = value.get("repository")
    providers = value.get("providers")
    if (
        not isinstance(repository, str)
        or contains_non_scalar(repository)
        or not REPOSITORY.fullmatch(repository)
    ):
        raise IndexNavigationViewerError("index graph repository is invalid")
    if not isinstance(providers, list):
        raise IndexNavigationViewerError("index graph providers must be an array")
    names = [
        provider.get("name") if isinstance(provider, dict) else None
        for provider in providers
    ]
    if names != list(PROVIDER_ORDER):
        raise IndexNavigationViewerError(
            "index graph providers must be ordered exactly as: " + ", ".join(PROVIDER_ORDER)
        )
    return value


def validate_repository_path(value: str, label: str) -> None:
    if (
        not value
        or contains_non_scalar(value)
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
    ):
        raise IndexNavigationViewerError(f"{label} is not a safe repository-relative path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise IndexNavigationViewerError(f"{label} is not a safe repository-relative path")
    if path.as_posix() != value:
        raise IndexNavigationViewerError(
            f"{label} is not a canonical repository-relative path"
        )


def is_index_source_path(value: str) -> bool:
    return value == "index.md" or value.endswith("/index.md")


def validate_plain_heading(value: str, label: str) -> None:
    """Validate producer-normalized heading text without reinterpreting Markdown syntax."""
    if contains_non_scalar(value) or contains_disallowed_control(
        value, allow_layout_whitespace=False
    ):
        raise IndexNavigationViewerError(
            f"{label} contains an invalid Unicode/control character"
        )


def _section_title(section: Any) -> str:
    if isinstance(section, str):
        if not section or contains_non_scalar(section):
            raise IndexNavigationViewerError("index section title is invalid")
        return section
    if not isinstance(section, dict):
        raise IndexNavigationViewerError("index section must be a string or object")
    title = section.get("title")
    level = section.get("level")
    if not isinstance(title, str) or not title or contains_non_scalar(title):
        raise IndexNavigationViewerError("index section title is invalid")
    if type(level) is not int or level < 2 or level > 6:
        raise IndexNavigationViewerError("index section level is invalid")
    return title


def _section_level(section: Any) -> int:
    if isinstance(section, str):
        return 2
    level = section.get("level") if isinstance(section, dict) else None
    if type(level) is not int or level < 2 or level > 6:
        raise IndexNavigationViewerError("index section level is invalid")
    return level


def validate_provider_graph(provider: dict[str, Any]) -> None:
    name = provider.get("name")
    revision = provider.get("revision")
    root_index = provider.get("root_index")
    indexes = provider.get("indexes")
    edges = provider.get("edges")
    diagnostics = provider.get("diagnostics")
    if not isinstance(name, str) or name not in PROVIDER_ORDER:
        raise IndexNavigationViewerError("provider name is invalid")
    if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
        raise IndexNavigationViewerError(f"{name} revision is invalid")
    if root_index != ROOT_INDEX:
        raise IndexNavigationViewerError(f"{name} root index is invalid")
    if not isinstance(indexes, list) or not indexes:
        raise IndexNavigationViewerError(f"{name} indexes must be a non-empty array")
    if not isinstance(edges, list) or not isinstance(diagnostics, dict):
        raise IndexNavigationViewerError(f"{name} graph shape is invalid")
    for field in ("index_count", "edge_count", "max_index_depth"):
        numeric = diagnostics.get(field)
        if type(numeric) is not int or numeric < 0:
            raise IndexNavigationViewerError(f"{name} diagnostics are invalid")

    paths: set[str] = set()
    index_by_path: dict[str, dict[str, Any]] = {}
    section_titles_by_path: dict[str, set[str]] = {}
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
            or not is_index_source_path(path)
            or not isinstance(title, str)
            or not title
            or contains_non_scalar(title)
            or not isinstance(sections, list)
            or type(depth) is not int
            or depth < 0
            or not isinstance(object_id, str)
            or not FULL_SHA.fullmatch(object_id)
        ):
            raise IndexNavigationViewerError(f"{name} index record is invalid")
        validate_repository_path(path, f"{name} index path")
        validate_plain_heading(title, f"{name} index title")
        section_titles = [_section_title(section) for section in sections]
        for section_title in section_titles:
            validate_plain_heading(section_title, f"{name} section heading")
        if len(set(section_titles)) != len(section_titles):
            raise IndexNavigationViewerError(
                f"{name} index contains duplicate section headings: {path}"
            )
        if path in paths:
            raise IndexNavigationViewerError(
                f"{name} graph contains duplicate index path: {path}"
            )
        paths.add(path)
        index_by_path[path] = index
        section_titles_by_path[path] = set(section_titles)

    if ROOT_INDEX not in paths:
        raise IndexNavigationViewerError(f"{name} graph does not contain its root index")

    allowed_kinds = {"index", "file", "directory", "fragment", "external"}
    for edge in edges:
        if not isinstance(edge, dict):
            raise IndexNavigationViewerError(f"{name} edge must be an object")
        source = edge.get("source")
        if source not in paths:
            raise IndexNavigationViewerError(f"{name} edge source is not a rendered index")
        kind = edge.get("kind")
        if kind not in allowed_kinds:
            raise IndexNavigationViewerError(f"{name} edge kind is invalid")
        text_fields = ("label", "description", "raw_target", "target")
        if not all(
            isinstance(edge.get(field), str)
            and not contains_non_scalar(edge[field])
            for field in text_fields
        ):
            raise IndexNavigationViewerError(f"{name} edge text fields are invalid")
        if type(edge.get("line")) is not int or edge["line"] < 1:
            raise IndexNavigationViewerError(f"{name} edge line is invalid")

        section = edge.get("section")
        fragment = edge.get("fragment")
        if section is not None and (
            not isinstance(section, str) or contains_non_scalar(section)
        ):
            raise IndexNavigationViewerError(f"{name} edge section is invalid")
        if section is not None and section not in section_titles_by_path[source]:
            raise IndexNavigationViewerError(
                f"{name} edge section is not declared by its index"
            )
        if fragment is not None and (
            not isinstance(fragment, str)
            or contains_non_scalar(fragment)
            or contains_disallowed_control(fragment, allow_layout_whitespace=False)
        ):
            raise IndexNavigationViewerError(f"{name} edge fragment is invalid")

        target = edge["target"]
        if kind == "external":
            try:
                parsed = urlsplit(target)
                parsed.port
                validate_external_location(parsed, source, edge["line"], target)
            except (ValueError, IndexNavigationError) as exc:
                raise IndexNavigationViewerError(
                    f"{name} external edge target is invalid"
                ) from exc
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.query
                or parsed.fragment
            ):
                raise IndexNavigationViewerError(
                    f"{name} external edge target is invalid"
                )
        elif not (kind == "directory" and target == "."):
            validate_repository_path(target, f"{name} edge target")

        if kind == "fragment" and target != source:
            raise IndexNavigationViewerError(
                f"{name} fragment edge must target its source index"
            )
        if kind == "index" and target not in paths:
            raise IndexNavigationViewerError(
                f"{name} index edge targets a non-rendered index: {target}"
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
    try:
        (guided / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
    except BaseException:
        shutil.rmtree(guided, ignore_errors=True)
        raise
    return guided


def encoded_path(parts: tuple[str, ...]) -> str:
    return "/".join(quote(part, safe="") for part in parts)


def index_page_path(provider: str, source_path: str) -> Path:
    validate_repository_path(source_path, "index source path")
    if not is_index_source_path(source_path):
        raise IndexNavigationViewerError(f"not an index source path: {source_path}")
    if source_path == ROOT_INDEX:
        return GUIDED_ROOT / provider / "index.html"
    if source_path == "index.md":
        return GUIDED_ROOT / ROOT_INDEX_NAMESPACE / provider / "index.html"
    parent = PurePosixPath(source_path).parent
    return GUIDED_ROOT / provider / Path(parent.as_posix()) / "index.html"


def index_page_url(provider: str, source_path: str) -> str:
    validate_repository_path(source_path, "index source path")
    if not is_index_source_path(source_path):
        raise IndexNavigationViewerError(f"not an index source path: {source_path}")
    if source_path == ROOT_INDEX:
        return f"/guided/{quote(provider, safe='')}/"
    if source_path == "index.md":
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
) -> tuple[str, str, bool]:
    kind = edge["kind"]
    target = edge["target"]
    fragment = edge.get("fragment")
    if kind == "index":
        return (
            index_page_url(provider, target) + fragment_suffix(fragment),
            "index",
            False,
        )
    if kind == "fragment":
        return fragment_suffix(fragment), "same index", False
    if kind == "external":
        return target + fragment_suffix(fragment), "external", True
    if kind == "directory":
        if fragment is None:
            return (
                f"/files/{quote(provider, safe='')}/",
                "repository directory",
                False,
            )
        if repository is None:
            raise IndexNavigationViewerError(
                "repository is required for a directory fragment"
            )
        source = github_url(
            repository,
            revision,
            "tree",
            immutable_edge_path(kind, target),
        )
        return source + fragment_suffix(fragment), "immutable directory", True
    if kind == "file":
        destination = published.get(target)
        if destination is not None:
            return (
                published_url("/", destination) + fragment_suffix(fragment),
                "published document",
                False,
            )
        if fragment is not None:
            if repository is None:
                raise IndexNavigationViewerError(
                    "repository is required for a source-file fragment"
                )
            source = github_url(
                repository, revision, "blob", target.encode("utf-8")
            )
            return source + fragment_suffix(fragment), "immutable source", True
        relative = viewer_relative_url(provider, revision, target.encode("utf-8"))
        return (
            f"/files/{quote(provider, safe='')}/{relative}",
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
    return github_url(
        repository,
        revision,
        git_kind,
        immutable_edge_path(kind, target),
    )


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
    edges: list[dict[str, Any]] | None = None,
    indexes: dict[str, dict[str, Any]] | None = None,
    parents: dict[str, tuple[str, str]] | None = None,
) -> str:
    source_path = index["path"]
    source = github_url(
        repository,
        provider["revision"],
        "blob",
        source_path.encode("utf-8"),
    )
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
        f'<p><strong>Revision:</strong> <code>{html.escape(provider["revision"])}</code></p>',
        f'<p><strong>Source:</strong> <code>{html.escape(source_path)}</code> · <a href="{html.escape(source, quote=True)}" target="_blank" rel="noopener">immutable GitHub source</a></p>',
        f'<p><strong>Repository:</strong> <a href="/files/{quote(provider["name"], safe="")}/">browse the same snapshot</a></p>',
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
        index_page_url(provider["name"], source_path),
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
            f'<p><code>{html.escape(provider["revision"])}</code></p>'
            f'<p>{index_count} reachable indexes · '
            f'{edge_count} links · '
            f'maximum index depth {max_depth}</p>'
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
    return page_shell("Index-guided document discovery", body, "/guided/")


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