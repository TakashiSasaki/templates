#!/usr/bin/env python3
"""Generate sandboxed inline previews for immutable repository-tree files."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
if __package__ in (None, ""):
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import html
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        configured_base_path,
        display_bytes,
        entry_label,
        github_url,
        parse_publications,
        published_sources,
        read_entries,
    )
except ModuleNotFoundError:
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        configured_base_path,
        display_bytes,
        entry_label,
        github_url,
        parse_publications,
        published_sources,
        read_entries,
    )


from publication_bundle.repository import (
    MAX_PREVIEW_BYTES,
    MAX_CANDIDATE_BYTES,
    MAX_TOTAL_PREVIEW_BYTES,
    BIDIRECTIONAL_CONTROLS,
    RepositoryFilePreviewError,
    PreviewRecord,
    decode_preview_text,
    preview_relative_url,
)
from site_renderer.previews import (
    TREE_CONTAINER,
    render_preview_page,
    viewer_panel,
    inject_preview_links,
    write_preview_pages,
)
PREVIEW_ROOT = Path("repository-trees/previews")






from integration.repository import (
    run_git_batch,
    object_sizes,
    object_contents,
    build_preview_records,
)




















def generate_previews(
    repository: str,
    site_root: Path,
    output_root: Path,
    publications: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryFilePreviewError("repository must use owner/name form")
    expected = {"skill", "policy", "webapp"}
    if set(publications) != expected:
        raise RepositoryFilePreviewError(
            "inline previews require exactly skill, policy, and webapp"
        )
    site_base_path = configured_base_path(output_root / "zensical.toml")
    messages: list[str] = []
    for publication in ("skill", "policy", "webapp"):
        root = publications[publication].resolve(strict=True)
        revision = checked_revision(root)
        records = build_preview_records(
            publication,
            repository,
            revision,
            root,
        )
        published = published_sources(publication, root, site_root)
        inject_preview_links(
            publication,
            repository,
            revision,
            site_base_path,
            output_root,
            published,
            records,
        )
        count = write_preview_pages(
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
            parse_publications(args.publication),
        )
    except (OSError, RepositoryTreeError, RepositoryFilePreviewError) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
