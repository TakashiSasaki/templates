"""Public validation for the integrated guided-navigation read model."""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from publication_bundle.repository import FULL_SHA, REPOSITORY
from publication_bundle.url_contract import IndexNavigationError, contains_disallowed_control, validate_external_location
PROVIDER_ORDER = ('composition', 'policy')
GRAPH_SCHEMA_VERSION = 2
LEGACY_GRAPH_SCHEMA_VERSION = 1
ROOT_INDEX = 'index.md'
LEGACY_ROOT_INDEX = 'docs/index.md'

class IndexNavigationViewerError(RuntimeError):
    """Raised when a guided-navigation viewer cannot be rendered safely."""


def contains_non_scalar(value: str) -> bool:
    """Return whether a Python string contains a Unicode surrogate code point."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def load_graph(path: Path, *, provider_order=PROVIDER_ORDER) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise IndexNavigationViewerError(f"graph must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndexNavigationViewerError(f"unable to read index graph {path}: {exc}") from exc
    schema_version = value.get("schema_version") if isinstance(value, dict) else None
    if type(schema_version) is not int or schema_version not in {LEGACY_GRAPH_SCHEMA_VERSION, GRAPH_SCHEMA_VERSION}:
        raise IndexNavigationViewerError("index graph must use schema_version 1 or 2")
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
    if names != list(provider_order):
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


def validate_provider_graph(
    provider: dict[str, Any],
    *,
    provider_order=PROVIDER_ORDER,
    root_index: str = ROOT_INDEX,
) -> None:
    name = provider.get("name")
    revision = provider.get("revision")
    indexes = provider.get("indexes")
    edges = provider.get("edges")
    diagnostics = provider.get("diagnostics")
    if not isinstance(name, str) or name not in provider_order:
        raise IndexNavigationViewerError("provider name is invalid")
    if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
        raise IndexNavigationViewerError(f"{name} revision is invalid")
    if provider.get("root_index") != root_index:
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

    if root_index not in paths:
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

    expected_diagnostics = graph_diagnostics(indexes, edges, root_index=root_index)
    if set(diagnostics) != set(expected_diagnostics):
        raise IndexNavigationViewerError(f"{name} diagnostics fields do not match producer contract")
    for field, expected in expected_diagnostics.items():
        if diagnostics[field] != expected:
            raise IndexNavigationViewerError(
                f"{name} diagnostics {field} does not match graph contents"
            )


def find_cycle_edges(
    adjacency: dict[str, list[str]],
    root: str,
) -> list[dict[str, str]]:
    cycle_edges: list[dict[str, str]] = []
    cycle_pairs: set[tuple[str, str]] = set()
    visiting: set[str] = {root}
    visited: set[str] = set()
    stack: list[tuple[str, int]] = [(root, 0)]

    while stack:
        node, next_index = stack[-1]
        targets = adjacency.get(node, [])
        if next_index >= len(targets):
            stack.pop()
            visiting.discard(node)
            visited.add(node)
            continue
        target = targets[next_index]
        stack[-1] = (node, next_index + 1)
        if target in visiting:
            pair = (node, target)
            if pair not in cycle_pairs:
                cycle_pairs.add(pair)
                cycle_edges.append({"source": node, "target": target})
            continue
        if target in visited:
            continue
        visiting.add(target)
        stack.append((target, 0))

    return cycle_edges


def graph_diagnostics(indexes, edges, *, root_index: str = ROOT_INDEX):
    """One deterministic diagnostic derivation for producers and consumers."""
    adjacency = {}
    incoming_sources = {}
    for edge in edges:
        if edge["kind"] == "index":
            adjacency.setdefault(edge["source"], []).append(edge["target"])
            incoming_sources.setdefault(edge["target"], set()).add(edge["source"])
    depths = {root_index: 0}
    queue = [root_index]
    cursor = 0
    while cursor < len(queue):
        source = queue[cursor];cursor += 1
        for target in adjacency.get(source, []):
            if target not in depths:
                depths[target] = depths[source] + 1
                queue.append(target)
    if {index["path"] for index in indexes} != set(depths):
        raise IndexNavigationViewerError("graph contains indexes unreachable from its root")
    if any(index["depth"] != depths[index["path"]] for index in indexes):
        raise IndexNavigationViewerError("graph index depth does not match root reachability")
    return {
        "index_count": len(indexes),
        "edge_count": len(edges),
        "max_index_depth": max((index["depth"] for index in indexes), default=0),
        "cycle_edges": find_cycle_edges(adjacency, root_index),
        "multiple_parent_indexes": sorted(path for path, sources in incoming_sources.items() if len(sources) > 1),
    }
