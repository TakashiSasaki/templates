#!/usr/bin/env python3
"""Generate the Skill copyable-template subtree page from a locked checkout."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

try:
    from .generate_repository_trees import (
        REPOSITORY,
        RepositoryTreeError,
        build_tree,
        checked_revision,
        configured_base_path,
        github_url,
        published_sources,
        read_entries,
        render_tree,
        replace_marker,
    )
except ImportError:
    from generate_repository_trees import (
        REPOSITORY,
        RepositoryTreeError,
        build_tree,
        checked_revision,
        configured_base_path,
        github_url,
        published_sources,
        read_entries,
        render_tree,
        replace_marker,
    )


TREE_MARKER = "<!-- GENERATED_SKILL_TEMPLATE_TREE -->"
SUMMARY_MARKER = "<!-- GENERATED_SKILL_TEMPLATE_SUMMARY -->"
DISTRIBUTION_PATH = b"template"


def generate(
    repository: str,
    site_root: Path,
    output_root: Path,
    skill_root: Path,
) -> str:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryTreeError("repository must use owner/name form")

    root = skill_root.resolve(strict=True)
    revision = checked_revision(root)
    tree = build_tree(read_entries(root))
    distribution = tree.children.get(DISTRIBUTION_PATH)
    if distribution is None or not distribution.is_directory:
        raise RepositoryTreeError(
            "skill repository does not contain a tracked template directory"
        )

    docs_root = output_root / "docs" / "repository-trees"
    page = docs_root / "skill" / "template.md"
    overview = docs_root / "overview.md"
    if not page.is_file() or not overview.is_file():
        raise RepositoryTreeError(
            "assembled Skill template-tree templates are missing"
        )

    site_base_path = configured_base_path(output_root / "zensical.toml")
    published = published_sources("skill", root, site_root)
    rendered, counts = render_tree(
        "skill",
        repository,
        revision,
        distribution,
        "repository-trees/skill/template.md",
        site_base_path,
        published,
    )

    distribution_url = html.escape(
        github_url(repository, revision, "tree", DISTRIBUTION_PATH),
        quote=True,
    )
    lines = rendered.splitlines()
    if not lines or not lines[0].startswith("**Rendered revision:**"):
        raise RepositoryTreeError("unexpected repository-tree rendering header")
    lines[0] = (
        f"**Copyable root:** [`template/`]({distribution_url}) at revision "
        f"[`{revision}`]({distribution_url})"
    )
    rendered = "\n".join(lines) + "\n"
    replace_marker(page, TREE_MARKER, rendered)

    summary = (
        "| [Skill copyable template](skill/template.md) | "
        f"`{revision}` | {counts['directories']} | {counts['files']} | "
        f"{counts['symlinks']} | {counts['gitlinks']} | "
        f"{counts['published_documents']} |"
    )
    replace_marker(overview, SUMMARY_MARKER, summary)

    return f"skill template: {counts['files']} files at {revision}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    try:
        message = generate(
            arguments.repository,
            arguments.site_root,
            arguments.output_root,
            arguments.skill_root,
        )
    except (OSError, RepositoryTreeError) as exc:
        raise SystemExit(f"skill template-tree generation failed: {exc}") from exc
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
