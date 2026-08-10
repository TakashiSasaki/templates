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
from urllib.parse import unquote_to_bytes, urlsplit, urlunsplit

try:
    from scripts.generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        RepositoryFilePreviewError,
        object_contents,
        object_sizes,
    )
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        read_entries,
    )
except ModuleNotFoundError:
    from generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        RepositoryFilePreviewError,
        object_contents,
        object_sizes,
    )
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        read_entries,
    )


PROVIDER_ORDER = ("skill", "policy", "webapp")
ROOT_INDEX = "docs/index.md"
MAX_INDEX_BYTES = 256 * 1024
REGULAR_FILE_MODES = frozenset({"100644", "100755"})
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
LINK_ENTRY = re.compile(
    r"^[*-][ \t]+\[([^\]]+)\]\((.+?)\)[ \t]+[-–—][ \t]+(.+?)\s*$"
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
    sections: tuple[str, ...]
    links: tuple[ParsedLink, ...]


def contains_disallowed_control(
    value: str,
    *,
    allow_layout_whitespace: bool = True,
) -> bool:
    for character in value:
        codepoint = ord(character)
        if (
            (codepoint < 32 and (not allow_layout_whitespace or character not in "\t\n\r"))
            or codepoint == 127
            or character in BIDIRECTIONAL_CONTROLS
        ):
            return True
    return False


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
    if contains_disallowed_control(text):
        raise IndexNavigationError(
            f"index contains a disallowed control character: {path}"
        )
    return text


def parse_index(text: str, path: str) -> ParsedIndex:
    title: str | None = None
    section: str | None = None
    sections: list[str] = []
    section_names: set[str] = set()
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
                if value in section_names:
                    raise IndexNavigationError(
                        f"duplicate section heading in {path}:{line_number}: {value!r}"
                    )
                section_names.add(value)
                section = value
                sections.append(value)
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
    return ParsedIndex(
        title=title,
        sections=tuple(sections),
        links=tuple(links),
    )


def decode_fragment(value: str, source: str, line: int) -> str | None:
    if not value:
        return None
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(
            f"link fragment is not UTF-8 in {source}:{line}: {value!r}"
        ) from exc
    if "\x00" in decoded:
        raise IndexNavigationError(
            f"link fragment contains a NUL byte in {source}:{line}: {value!r}"
        )
    if contains_disallowed_control(decoded, allow_layout_whitespace=False):
        raise IndexNavigationError(
            f"link fragment contains a disallowed control character in {source}:{line}: {value!r}"
        )
    return decoded


def decode_link_path(value: str, source: str, line: int) -> tuple[str, bool]:
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
    trailing_slash = decoded.endswith("/")
    normalized = posixpath.normpath(posixpath.join(posixpath.dirname(source), decoded))
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise IndexNavigationError(
            f"link escapes repository root in {source}:{line}: {value!r}"
        )
    return normalized, trailing_slash


def validate_external_location(parsed: object, source: str, line: int, target: str) -> None:
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if not hostname:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )


def resolve_link(
    source: str,
    link: ParsedLink,
    entries: dict[str, tuple[str, str, str]],
) -> dict[str, object]:
    target = link.raw_target
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed link target in {source}:{link.line}: {target!r}"
        ) from exc
    fragment = decode_fragment(parsed.fragment, source, link.line)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise IndexNavigationError(
                f"unsupported external link in {source}:{link.line}: {target!r}"
            )
        validate_external_location(parsed, source, link.line, target)
        if parsed.query:
            raise IndexNavigationError(
                f"external link must not contain a query in {source}:{link.line}: {target!r}"
            )
        external_target = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
        return {
            "kind": "external",
            "target": external_target,
            "fragment": fragment,
        }
    if parsed.query:
        raise IndexNavigationError(
            f"repository link must not contain a query in {source}:{link.line}: {target!r}"
        )
    if not parsed.path:
        if fragment is None:
            raise IndexNavigationError(
                f"empty link target in {source}:{link.line}"
            )
        return {
            "kind": "fragment",
            "target": source,
            "fragment": fragment,
        }

    normalized, trailing_slash = decode_link_path(parsed.path, source, link.line)
    target_entry = entries.get(normalized)
    if trailing_slash and target_entry is not None and target_entry[0] == "blob":
        raise IndexNavigationError(
            f"slash-terminated repository link targets a regular file in {source}:{link.line}: {target!r}"
        )
    if target_entry is None and trailing_slash:
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
    elif kind == "blob" and mode in REGULAR_FILE_MODES:
        resolved_kind = "index" if normalized.endswith("/index.md") else "file"
    else:
        raise IndexNavigationError(
            f"link target is not a regular file or directory in {source}:{link.line}: {normalized}"
        )
    return {
        "kind": resolved_kind,
        "target": normalized,
        "fragment": fragment,
    }


def load_reachable_index(
    root: Path,
    path: str,
    entry: tuple[str, str, str] | None,
) -> tuple[str, ParsedIndex]:
    if entry is None or entry[0] != "blob" or entry[1] not in REGULAR_FILE_MODES:
        raise IndexNavigationError(f"linked index.md is not a regular file: {path}")
    object_id = entry[2]
    size = object_sizes(root, [object_id])[object_id]
    if size > MAX_INDEX_BYTES:
        raise IndexNavigationError(
            f"index exceeds {MAX_INDEX_BYTES // 1024} KiB limit: {path}"
        )
    content = object_contents(root, [object_id])[object_id]
    return object_id, parse_index(decode_index_text(content, path), path)


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


def collect_provider_graph(provider: str, root: Path) -> dict[str, object]:
    revision = checked_revision(root)
    entries_list = read_entries(root)
    entries: dict[str, tuple[str, str, str]] = {}
    for entry in entries_list:
        try:
            path = entry.path.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise IndexNavigationError(
                f"provider contains a non-UTF-8 repository path: {entry.path!r}"
            ) from exc
        entries[path] = (entry.kind, entry.mode, entry.object_id)

    root_entry = entries.get(ROOT_INDEX)
    if (
        root_entry is None
        or root_entry[0] != "blob"
        or root_entry[1] not in REGULAR_FILE_MODES
    ):
        raise IndexNavigationError(
            f"{provider} root navigation index must be a regular file: {ROOT_INDEX}"
        )

    queue: deque[tuple[str, int]] = deque([(ROOT_INDEX, 0)])
    seen: set[str] = set()
    queued: set[str] = {ROOT_INDEX}
    indexes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    depths: dict[str, int] = {ROOT_INDEX: 0}
    incoming_sources: dict[str, set[str]] = {}

    while queue:
        path, depth = queue.popleft()
        queued.discard(path)
        if path in seen:
            continue
        seen.add(path)
        object_id, parsed_index = load_reachable_index(root, path, entries.get(path))
        indexes.append(
            {
                "path": path,
                "title": parsed_index.title,
                "sections": list(parsed_index.sections),
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
                incoming_sources.setdefault(target_path, set()).add(path)
                candidate_depth = depth + 1
                previous = depths.get(target_path)
                if previous is None or candidate_depth < previous:
                    depths[target_path] = candidate_depth
                if target_path not in seen and target_path not in queued:
                    queue.append((target_path, depths[target_path]))
                    queued.add(target_path)

    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge["kind"] == "index":
            adjacency.setdefault(str(edge["source"]), []).append(str(edge["target"]))

    cycle_edges = find_cycle_edges(adjacency, ROOT_INDEX)
    max_depth = max((int(index["depth"]) for index in indexes), default=0)
    return {
        "name": provider,
        "revision": revision,
        "root_index": ROOT_INDEX,
        "indexes": sorted(
            indexes,
            key=lambda value: (int(value["depth"]), str(value["path"])),
        ),
        "edges": edges,
        "diagnostics": {
            "index_count": len(indexes),
            "edge_count": len(edges),
            "max_index_depth": max_depth,
            "cycle_edges": cycle_edges,
            "multiple_parent_indexes": sorted(
                path for path, sources in incoming_sources.items() if len(sources) > 1
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
        for provider in graph["providers"]:
            diagnostics = provider["diagnostics"]
            print(
                f"{provider['name']} index navigation: "
                f"{diagnostics['index_count']} indexes, "
                f"{diagnostics['edge_count']} links, "
                f"depth {diagnostics['max_index_depth']} @ {provider['revision']}"
            )
    except (IndexNavigationError, RepositoryTreeError, RepositoryFilePreviewError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
