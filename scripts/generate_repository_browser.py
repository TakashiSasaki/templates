#!/usr/bin/env python3
"""Generate a standalone static browser for immutable repository revisions."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
if __package__ in (None, ""):
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import html
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_from_bytes

from pygments import lex
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

try:
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        TreeEntry,
        build_tree,
        checked_revision,
        display_bytes,
        entry_label,
        read_entries,
    )
    from scripts.generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        RepositoryFilePreviewError,
        object_contents,
        object_sizes,
    )
except ModuleNotFoundError:
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        TreeEntry,
        build_tree,
        checked_revision,
        display_bytes,
        entry_label,
        read_entries,
    )
    from generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        RepositoryFilePreviewError,
        object_contents,
        object_sizes,
    )


from site_renderer.repository_browser import (
    human_size,
    branch_nav,
    render_tree_entry,
    render_browser_page,
    lexer_for,
    highlighted_lines,
    pygments_css,
    validate_line_anchor_invariant,
    render_file_page,
    write_verified_file_page,
    prepare_browser_root,
    write_root_index,
    write_browser_controller,
    BRANCH_ORDER,
    BROWSER_ROOT,
    MANAGED_MARKER,
    MANAGED_MARKER_CONTENT,
    CONTROLLER_NAME,
    CONTROLLER_SOURCE,
)
from publication_bundle.repository import (
    MAX_TEXT_BYTES,
    MAX_TOTAL_TEXT_BYTES,
    RepositoryBrowserError,
    FileRecord,
    decode_browser_text,
    source_url,
    viewer_relative_url,
)












from integration.repository import (
    collect_records,
)




























def generate_browser(
    repository: str,
    output_root: Path,
    branches: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryBrowserError("repository must use owner/name form")
    if tuple(branches) != BRANCH_ORDER:
        raise RepositoryBrowserError(
            "branches must be supplied exactly in site, composition, policy order"
        )
    browser_root = prepare_browser_root(output_root)
    write_root_index(browser_root)
    write_browser_controller(browser_root)
    messages: list[str] = []
    for branch in BRANCH_ORDER:
        root = branches[branch].resolve(strict=True)
        revision = checked_revision(root)
        if not FULL_SHA.fullmatch(revision):
            raise RepositoryBrowserError(
                f"{branch} did not resolve to a full SHA"
            )
        tree, records = collect_records(
            branch,
            repository,
            revision,
            root,
        )
        branch_root = browser_root / branch
        content_root = branch_root / "content"
        content_root.mkdir(parents=True)
        branch_root.joinpath("index.html").write_text(
            render_browser_page(branch, revision, tree, records),
            encoding="utf-8",
        )
        for record in records.values():
            destination = branch_root / record.viewer_url
            write_verified_file_page(destination, branch, revision, record)
        messages.append(
            f"{branch}: {sum(record.viewable for record in records.values())}/"
            f"{len(records)} regular files browser-viewable at {revision}"
        )
    return messages


def parse_branch(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("branch must use name=path form")
    name, raw_path = value.split("=", 1)
    if name not in BRANCH_ORDER or not raw_path:
        raise argparse.ArgumentTypeError(
            "branch name must be site, composition, or policy"
        )
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--branch",
        action="append",
        type=parse_branch,
        required=True,
    )
    args = parser.parse_args()
    branches: dict[str, Path] = {}
    for name, path in args.branch:
        if name in branches:
            parser.error(f"duplicate branch: {name}")
        branches[name] = path
    try:
        messages = generate_browser(
            args.repository,
            args.output_root,
            branches,
        )
    except (
        RepositoryBrowserError,
        RepositoryTreeError,
        RepositoryFilePreviewError,
        OSError,
    ) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
