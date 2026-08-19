#!/usr/bin/env python3
"""Generate repository-tree pages for the composition and policy providers."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import generate_repository_trees as base
except ModuleNotFoundError:
    import generate_repository_trees as base

PROVIDER_ORDER = ("composition", "policy")
LABELS = {
    "composition": "Composition",
    "policy": "Policy",
}


def generate(
    repository: str,
    site_root: Path,
    output_root: Path,
    publications: dict[str, Path],
) -> list[str]:
    if not base.REPOSITORY.fullmatch(repository):
        raise base.RepositoryTreeError("repository must use owner/name form")
    if tuple(publications) != PROVIDER_ORDER:
        raise base.RepositoryTreeError(
            "repository trees require exactly composition and policy in that order"
        )

    docs_root = output_root / "docs" / "repository-trees"
    if not docs_root.is_dir():
        raise base.RepositoryTreeError(
            f"assembled repository-tree templates are missing: {docs_root}"
        )

    site_base_path = base.configured_base_path(output_root / "zensical.toml")
    summaries: dict[str, tuple[str, dict[str, int]]] = {}
    messages: list[str] = []
    for publication in PROVIDER_ORDER:
        root = publications[publication].resolve(strict=True)
        revision = base.checked_revision(root)
        entries = base.read_entries(root)
        tree = base.build_tree(entries)
        tree_destination = f"repository-trees/{publication}.md"
        published = base.published_sources(publication, root, site_root)
        rendered, counts = base.render_tree(
            publication,
            repository,
            revision,
            tree,
            tree_destination,
            site_base_path,
            published,
        )
        base.replace_marker(
            docs_root / f"{publication}.md",
            f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->",
            rendered,
        )
        summaries[publication] = (revision, counts)
        messages.append(f"{publication}: {counts['files']} files at {revision}")

    table = [
        "| Publication | Rendered revision | Directories | Files | Published documents |",
        "|---|---|---:|---:|---:|",
    ]
    for publication in PROVIDER_ORDER:
        revision, counts = summaries[publication]
        table.append(
            f"| [{LABELS[publication]}]({publication}.md) | "
            f"`{revision}` | {counts['directories']} | "
            f"{counts['files'] + counts['symlinks'] + counts['gitlinks']} | "
            f"{counts['published_documents']} |"
        )
    base.replace_marker(
        docs_root / "index.md",
        base.INDEX_MARKER,
        "\n".join(table) + "\n",
    )
    return messages


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
        publications = base.parse_publications(args.publication)
        messages = generate(
            args.repository,
            args.site_root.resolve(strict=True),
            args.output_root.resolve(strict=True),
            publications,
        )
    except (OSError, base.RepositoryTreeError) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
