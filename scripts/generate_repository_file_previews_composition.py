#!/usr/bin/env python3
"""Generate inline previews for the composition and policy repository trees."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import generate_repository_file_previews as previews
    from scripts import generate_repository_trees as trees
except ModuleNotFoundError:
    import generate_repository_file_previews as previews
    import generate_repository_trees as trees

PROVIDER_ORDER = ("composition", "policy")


def generate_previews(
    repository: str,
    site_root: Path,
    output_root: Path,
    publications: dict[str, Path],
) -> list[str]:
    if not trees.REPOSITORY.fullmatch(repository):
        raise previews.RepositoryFilePreviewError("repository must use owner/name form")
    if tuple(publications) != PROVIDER_ORDER:
        raise previews.RepositoryFilePreviewError(
            "inline previews require exactly composition and policy in that order"
        )
    site_base_path = previews.configured_base_path(output_root / "zensical.toml")
    messages: list[str] = []
    for publication in PROVIDER_ORDER:
        root = publications[publication].resolve(strict=True)
        revision = trees.checked_revision(root)
        records = previews.build_preview_records(
            publication,
            repository,
            revision,
            root,
        )
        published = trees.published_sources(publication, root, site_root)
        previews.inject_preview_links(
            publication,
            repository,
            revision,
            site_base_path,
            output_root,
            published,
            records,
        )
        count = previews.write_preview_pages(
            output_root,
            records,
            publication,
            revision,
        )
        messages.append(
            f"{publication}: {count} inline text previews at {revision}"
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
        messages = generate_previews(
            args.repository,
            args.site_root.resolve(strict=True),
            args.output_root.resolve(strict=True),
            trees.parse_publications(args.publication),
        )
    except (OSError, trees.RepositoryTreeError, previews.RepositoryFilePreviewError) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
