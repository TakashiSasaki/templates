#!/usr/bin/env python3
"""Generate deterministic repository-tree pages for locked publications."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, quote_from_bytes, urlsplit

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.assemble_publications import AssemblyError, load_manifest


from publication_bundle.repository import (
    NAME,
    FULL_SHA,
    REPOSITORY,
    INDEX_MARKER,
    RepositoryTreeError,
    TreeEntry,
    parse_name,
    read_json,
    parse_ls_tree,
    build_tree,
    display_bytes,
    github_url,
    markdown_destination_url,
    configured_base_path,
    published_url,
    entry_label,
)










from integration.repository import (
    git,
    checked_revision,
    read_entries,
    manifest_destinations,
    published_sources,
)


























def render_entry(
    entry: TreeEntry,
    repository: str,
    revision: str,
    tree_destination: str,
    site_base_path: str,
    published: dict[bytes, str],
    depth: int,
) -> list[str]:
    indent = "  " * depth
    name = html.escape(display_bytes(entry.name), quote=False)
    path = entry.path

    if entry.is_directory:
        source = html.escape(
            github_url(repository, revision, "tree", path),
            quote=True,
        )
        values = [
            f'{indent}<details>',
            f'{indent}  <summary><code>{name}/</code> '
            f'<a href="{source}">GitHub</a></summary>',
            f'{indent}  <ul>',
        ]
        for child in sorted(
            entry.children.values(),
            key=lambda item: (not item.is_directory, item.name),
        ):
            values.append(f"{indent}    <li>")
            values.extend(
                render_entry(
                    child,
                    repository,
                    revision,
                    tree_destination,
                    site_base_path,
                    published,
                    depth + 3,
                )
            )
            values.append(f"{indent}    </li>")
        values.extend([f"{indent}  </ul>", f"{indent}</details>"])
        return values

    label = entry_label(entry)
    external_kind = "tree" if label == "gitlink" else "blob"
    source = html.escape(
        github_url(repository, revision, external_kind, path),
        quote=True,
    )
    type_suffix = "" if label == "file" else f" <small>({label})</small>"
    destination = published.get(path)
    if destination is not None and label == "file":
        internal = html.escape(
            published_url(site_base_path, destination),
            quote=True,
        )
        return [
            f'{indent}<code><a href="{internal}">{name}</a></code>'
            f'{type_suffix} <small><a href="{source}">source</a></small>'
        ]
    return [f'{indent}<code><a href="{source}">{name}</a></code>{type_suffix}']


def render_tree(
    publication: str,
    repository: str,
    revision: str,
    root: TreeEntry,
    tree_destination: str,
    site_base_path: str,
    published: dict[bytes, str],
) -> tuple[str, dict[str, int]]:
    entries: list[TreeEntry] = []

    def collect(node: TreeEntry) -> None:
        for child in node.children.values():
            entries.append(child)
            if child.is_directory:
                collect(child)

    collect(root)
    counts = {
        "directories": sum(entry.is_directory for entry in entries),
        "files": sum(entry_label(entry) == "file" for entry in entries),
        "symlinks": sum(entry_label(entry) == "symlink" for entry in entries),
        "gitlinks": sum(entry_label(entry) == "gitlink" for entry in entries),
        "published_documents": sum(
            entry.path in published and entry_label(entry) == "file"
            for entry in entries
        ),
    }

    root_url = html.escape(
        github_url(repository, revision, "tree"),
        quote=True,
    )

    def quantity(value: int, singular: str) -> str:
        suffix = "" if value == 1 else "s"
        return f"{value} {singular}{suffix}"

    values = [
        f"**Rendered revision:** [`{revision}`]({root_url})",
        "",
        (
            "Tracked tree: "
            f"{quantity(counts['directories'], 'directory')}, "
            f"{quantity(counts['files'], 'regular file')}, "
            f"{quantity(counts['symlinks'], 'symlink')}, and "
            f"{quantity(counts['gitlinks'], 'gitlink')}. "
            f"Documentation pages: {counts['published_documents']}."
        ),
        "",
        "File names link to the human-readable documentation page when the file is "
        "cataloged; otherwise they link to the immutable GitHub source view. "
        "The adjacent **source** link always opens GitHub at the same revision.",
        "",
        '<div class="repository-tree">',
        "<ul>",
    ]
    for child in sorted(
        root.children.values(),
        key=lambda item: (not item.is_directory, item.name),
    ):
        values.append("  <li>")
        values.extend(
            render_entry(
                child,
                repository,
                revision,
                tree_destination,
                site_base_path,
                published,
                2,
            )
        )
        values.append("  </li>")
    values.extend(["</ul>", "</div>"])
    return "\n".join(values) + "\n", counts


def replace_marker(path: Path, marker: str, content: str) -> None:
    try:
        template = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RepositoryTreeError(f"unable to read tree template {path}: {exc}") from exc
    if template.count(marker) != 1:
        raise RepositoryTreeError(
            f"{path} must contain {marker!r} exactly once"
        )
    path.write_text(template.replace(marker, content.rstrip()), encoding="utf-8")


def generate(
    repository: str,
    site_root: Path,
    output_root: Path,
    publications: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryTreeError("repository must use owner/name form")
    expected = {"skill", "policy", "webapp"}
    if set(publications) != expected:
        raise RepositoryTreeError(
            "repository trees require exactly skill, policy, and webapp"
        )

    docs_root = output_root / "docs" / "repository-trees"
    if not docs_root.is_dir():
        raise RepositoryTreeError(
            f"assembled repository-tree templates are missing: {docs_root}"
        )

    site_base_path = configured_base_path(output_root / "zensical.toml")
    summaries: dict[str, tuple[str, dict[str, int]]] = {}
    messages: list[str] = []
    for publication in ("skill", "policy", "webapp"):
        root = publications[publication].resolve(strict=True)
        revision = checked_revision(root)
        entries = read_entries(root)
        tree = build_tree(entries)
        tree_destination = f"repository-trees/{publication}.md"
        published = published_sources(publication, root, site_root)
        rendered, counts = render_tree(
            publication,
            repository,
            revision,
            tree,
            tree_destination,
            site_base_path,
            published,
        )
        replace_marker(
            docs_root / f"{publication}.md",
            f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->",
            rendered,
        )
        summaries[publication] = (revision, counts)
        messages.append(
            f"{publication}: {counts['files']} files at {revision}"
        )

    table = [
        "| Publication | Rendered revision | Directories | Files | Published documents |",
        "|---|---|---:|---:|---:|",
    ]
    labels = {
        "skill": "Skill",
        "policy": "Policy",
        "webapp": "Web application",
    }
    for publication in ("skill", "policy", "webapp"):
        revision, counts = summaries[publication]
        table.append(
            f"| [{labels[publication]}]({publication}.md) | "
            f"`{revision}` | {counts['directories']} | "
            f"{counts['files'] + counts['symlinks'] + counts['gitlinks']} | "
            f"{counts['published_documents']} |"
        )
    replace_marker(
        docs_root / "index.md",
        INDEX_MARKER,
        "\n".join(table) + "\n",
    )
    return messages


def parse_publications(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for index, value in enumerate(values):
        if "=" not in value:
            raise RepositoryTreeError(
                f"--publication[{index}] must use NAME=PATH"
            )
        name, raw_path = value.split("=", maxsplit=1)
        name = parse_name(name, f"--publication[{index}].name")
        if not raw_path or name in result:
            raise RepositoryTreeError(
                f"--publication[{index}] must have a unique non-empty path"
            )
        result[name] = Path(raw_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--publication",
        action="append",
        default=[],
        metavar="NAME=PATH",
    )
    args = parser.parse_args()

    try:
        messages = generate(
            args.repository,
            args.site_root.resolve(strict=True),
            args.output_root.resolve(strict=True),
            parse_publications(args.publication),
        )
    except RepositoryTreeError as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())