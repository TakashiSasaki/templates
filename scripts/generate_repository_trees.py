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


























from site_renderer.repository_trees import (
    render_entry,
    render_tree,
    replace_marker,
)






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