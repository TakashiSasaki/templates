#!/usr/bin/env python3
"""Generate a deterministic navigation graph from provider-owned index.md files."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit

try:
    from scripts.generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        object_contents,
        object_sizes,
    )
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        checked_revision,
        read_entries,
    )
except ModuleNotFoundError:
    from generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        object_contents,
        object_sizes,
    )
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        checked_revision,
        read_entries,
    )


PROVIDER_ORDER = ("skill", "policy", "webapp")
ROOT_INDEX = "docs/index.md"
MAX_INDEX_BYTES = 256 * 1024
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
LINK_ENTRY = re.compile(
    r"^[*-][ \t]+\[([^\]]+)\]\(([^)]+)\)[ \t]+[-—][ \t]+(.+?)\s*$"
)


class IndexNavigationError(RuntimeError):
    """Raised when an index navigation graph cannot be produced safely."""


@dataclass(frozen=True)
class ParsedLink:
    label: str
    raw_target: str
    description: str
    section: str | None
    line: int


@dataclass(frozen=True)
class ParsedIndex:
    title: str
    links: tuple[ParsedLink, ...]


def decode_index_text(content: bytes, path: str) -> str:
    if len(content) > MAX_INDEX_BYTES:
        raise IndexNavigationError(
            f"index exceeds {MAX_INDEX_BYTES // 1024} KiB limit: {path}"
        )
    if b"\0" in content:
        raise IndexNavigationError(f"index contains a NUL byte: {path}")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(f"index is not strict UTF-8: {path}") from exc
    for character in text:
        value = ord(character)
        if (
            (value < 32 and character not in "\t\n\r")
            or value == 127
            or character in BIDIRECTIONAL_CONTROLS
        ):
            raise IndexNavigationError(
                f"index contains a disallowed control character: {path}"
            )
    return text


def parse_index(text: str, path: str) -> ParsedIndex:
    title: str | None = None
    section: str | None = None
    links: list[ParsedLink] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        heading = HEADING.fullmatch(line)
        if heading:
            level = len(heading.group(1))
            value = heading.group(2).strip()
            if not value:
                raise IndexNavigationError(
                    f"empty heading in {path}:{line_number}"
                )
            if level == 1:
                if title is not None:
                    raise IndexNavigationError(
                        f"multiple level-1 headings in {path}:{line_number}"
                    )
                title = value
                section = None
            else:
                if title is None:
                    raise IndexNavigationError(
                        f"section precedes title in {path}:{line_number}"
                    )
                section = value
            continue
        entry = LINK_ENTRY.fullmatch(line)
        if entry:
            if title is None:
                raise IndexNavigationError(
                    f"link precedes title in {path}:{line_number}"
                )
            links.append(
                ParsedLink(
                    label=entry.group(1).strip(),
                    raw_target=entry.group(2).strip(),
                    description=entry.group(3).strip(),
                    section=section,
                    line=line_number,
                )
            )
            continue
        raise IndexNavigationError(
            f"unsupported index.md content in {path}:{line_number}: {raw_line!r}"
        )
    if title is None:
        raise IndexNavigationError(f"index is missing a level-1 heading: {path}")
    return ParsedIndex(title=title, links=tuple(links))


def decode_link_path(value: str, source: str, line: int) -> str:
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(
            f"link path is not UTF-8 in {source}:{line}: {value!r}"
        ) from exc
    if not decoded or decoded.startswith("/") or "\x00" in decoded:
        raise IndexNavigationError(
            f"unsafe repository-relative link in {source}:{line}: {value!r}"
        )
    normalized = posixpath.normpath(posixpath.join(posixpath.dirname(source), decoded))
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise IndexNavigationError(
            f"link escapes repository root in {source}:{line}: {value!r}"
        )
    return normalized


def resolve_link(
    source: str,
    link: ParsedLink,
    entries: dict[str, tuple[str, str, str]],
) -> dict[str, object]:
    target = link.raw_target
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise IndexNavigationError(
                f"unsupported external link in {source}:{link.line}: {target!r}"
            )
        return {
            "kind": "external",
            "target": target,
            "fragment": parsed.fragment or None,
        }
    if parsed.query:
        raise IndexNavigationError(
            f"repository link must not contain a query in {source}:{link.line}: {target!r}"
        )
    if not parsed.path:
        if not parsed.fragment:
            raise IndexNavigationError(
                f"empty link target in {source}:{link.line}"
            )
        return {
            "kind": "fragment",
            "target": source,
            "fragment": parsed.fragment,
        }

    normalized = decode_link_path(parsed.path, source, link.line)
    target_entry = entries.get(normalized)
    if target_entry is None and parsed.path.endswith("/"):
        candidate = normalized.rstrip("/") + "/index.md"
        if candidate in entries:
            normalized = candidate
            target_entry = entries[candidate]
    elif target_entry is not None and target_entry[0] == "tree":
        candidate = normalized.rstrip("/") + "/index.md"
        if candidate in entries:
            normalized = candidate
            target_entry = entries[candidate]

    if target_entry is None:
        raise IndexNavigationError(
            f"broken repository link in {source}:{link.line}: {target!r} -> {normalized}"
        )

    kind, mode, _object_id = target_entry
    if kind == "tree":
        resolved_kind = "directory"
    elif kind == "blob" and mode == "100644":
        resolved_kind = "index" if normalized.endswith("/index.md") else "file"
    else:
        raise IndexNavigationError(
            f"link target is not a regular file or directory in {source}:{link.line}: {normalized}"
        )
    return {
        "kind": resolved_kind,
        "target": normalized,
        "fragment": parsed.fragment or None,
    }


def collect_provider_graph(provider: str, root: Path) -> dict[str, object]:
    revision = checked_revision(root)
    entries_list = read_entries(root)
    entries = {
        entry.path.decode("utf-8", errors="strict"): (
            entry.kind,
            entry.mode,
            entry.object_id,
        )
        for entry in entries_list
    }
    root_entry = entries.get(ROOT_INDEX)
    if root_entry is None or root_entry[0] != "blob" or root_entry[1] != "100644":
        raise IndexNavigationError(
            f"{provider} root navigation index must be a regular file: {ROOT_INDEX}"
        )

    index_object_ids = {
        path: value[2]
        for path, value in entries.items()
        if path.endswith("/index.md") and value[0] == "blob" and value[1] == "100644"
    }
    sizes = object_sizes(root, index_object_ids.values())
    oversized = [
        path
        for path, object_id in index_object_ids.items()
        if sizes[object_id] > MAX_INDEX_BYTES
    ]
    if oversized:
        raise IndexNavigationError(
            f"provider contains oversized index.md: {', '.join(sorted(oversized))}"
        )
    contents = object_contents(root, index_object_ids.values())

    queue: deque[tuple[str, int]] = deque([(ROOT_INDEX, 0)])
    seen: set[str] = set()
    queued: set[str] = {ROOT_INDEX}
    indexes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    depths: dict[str, int] = {ROOT_INDEX: 0}
    incoming: dict[str, int] = {}

    while queue:
        path, depth = queue.popleft()
        queued.discard(path)
        if path in seen:
            continue
        seen.add(path)
        object_id = index_object_ids.get(path)
        if object_id is None:
            raise IndexNavigationError(f"linked index.md is not a regular file: {path}")
        parsed_index = parse_index(
            decode_index_text(contents[object_id], path),
            path,
        )
        indexes.append(
            {
                "path": path,
                "title": parsed_index.title,
                "depth": depth,
                "object_id": object_id,
            }
        )
        for link in parsed_index.links:
            resolved = resolve_link(path, link, entries)
            edge = {
                "source": path,
                "section": link.section,
                "label": link.label,
                "description": link.description,
                "line": link.line,
                "raw_target": link.raw_target,
                **resolved,
            }
            edges.append(edge)
            if resolved["kind"] == "index":
                target_path = str(resolved["target"])
                incoming[target_path] = incoming.get(target_path, 0) + 1
                candidate_depth = depth + 1
                previous = depths.get(target_path)
                if previous is None or candidate_depth < previous:
                    depths[target_path] = candidate_depth
                if target_path not in seen and target_path not in queued:
                    queue.append((target_path, depths[target_path]))
                    queued.add(target_path)

    index_edges = [edge for edge in edges if edge["kind"] == "index"]
    adjacency: dict[str, list[str]] = {}
    for edge in index_edges:
        adjacency.setdefault(str(edge["source"]), []).append(str(edge["target"]))

    cycle_edges: list[dict[str, str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency.get(node, []):
            if target in visiting:
                cycle_edges.append({"source": node, "target": target})
            elif target not in visited:
                visit(target)
        visiting.remove(node)
        visited.add(node)

    visit(ROOT_INDEX)
    max_depth = max((int(index["depth"]) for index in indexes), default=0)
    return {
        "name": provider,
        "revision": revision,
        "root_index": ROOT_INDEX,
        "indexes": sorted(indexes, key=lambda value: (int(value["depth"]), str(value["path"]))),
        "edges": edges,
        "diagnostics": {
            "index_count": len(indexes),
            "edge_count": len(edges),
            "max_index_depth": max_depth,
            "cycle_edges": cycle_edges,
            "multiple_parent_indexes": sorted(
                path for path, count in incoming.items() if count > 1
            ),
        },
    }


def parse_providers(values: list[str]) -> dict[str, Path]:
    providers: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise IndexNavigationError("provider must use NAME=PATH syntax")
        name, raw_path = value.split("=", maxsplit=1)
        if name in providers:
            raise IndexNavigationError(f"duplicate provider: {name}")
        providers[name] = Path(raw_path)
    if tuple(providers) != PROVIDER_ORDER:
        raise IndexNavigationError(
            "providers must be supplied exactly in this order: "
            + ", ".join(PROVIDER_ORDER)
        )
    return providers


def generate_graph(repository: str, providers: dict[str, Path]) -> dict[str, object]:
    if not REPOSITORY.fullmatch(repository):
        raise IndexNavigationError("repository must use owner/name syntax")
    if tuple(providers) != PROVIDER_ORDER:
        raise IndexNavigationError(
            "providers must be supplied exactly in this order: "
            + ", ".join(PROVIDER_ORDER)
        )
    graphs = [collect_provider_graph(name, providers[name]) for name in PROVIDER_ORDER]
    for graph in graphs:
        if not FULL_SHA.fullmatch(str(graph["revision"])):
            raise IndexNavigationError("provider revision is not a full lowercase SHA")
    return {
        "schema_version": 1,
        "repository": repository,
        "providers": graphs,
    }


def write_graph(output: Path, graph: dict[str, object]) -> None:
    if output.is_symlink():
        raise IndexNavigationError("output must not be a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider", action="append", default=[])
    args = parser.parse_args()
    try:
        providers = parse_providers(args.provider)
        graph = generate_graph(args.repository, providers)
        write_graph(args.output, graph)
    except IndexNavigationError as exc:
        parser.error(str(exc))
    for provider in graph["providers"]:
        diagnostics = provider["diagnostics"]
        print(
            f"{provider['name']} index navigation: "
            f"{diagnostics['index_count']} indexes, "
            f"{diagnostics['edge_count']} links, "
            f"depth {diagnostics['max_index_depth']} @ {provider['revision']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
