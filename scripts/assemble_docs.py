#!/usr/bin/env python3
"""Assemble canonical documentation into a temporary Zensical project."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, TypeAlias

NAV_PLACEHOLDER = "__GENERATED_NAV__"


class AssemblyError(RuntimeError):
    """Raised when the site manifest or source tree is invalid."""


@dataclass(frozen=True)
class Page:
    title: str
    source: PurePosixPath
    destination: PurePosixPath
    optional: bool
    field: str


@dataclass(frozen=True)
class Section:
    title: str
    children: tuple["NavigationNode", ...]
    field: str


NavigationNode: TypeAlias = Page | Section


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


def safe_relative_path(value: str, field: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise AssemblyError(f"{field} must be a non-empty relative path: {value!r}")
    return path


def parse_title(raw_node: dict[str, Any], field: str) -> str:
    title = raw_node.get("title")
    if not isinstance(title, str) or not title.strip():
        raise AssemblyError(f"{field}.title must be a non-empty string")
    return title.strip()


def parse_navigation_node(raw_node: Any, field: str) -> NavigationNode:
    if not isinstance(raw_node, dict):
        raise AssemblyError(f"{field} must be an object")

    title = parse_title(raw_node, field)
    has_children = "children" in raw_node
    has_page_field = any(key in raw_node for key in ("source", "destination", "optional"))

    if has_children:
        if has_page_field:
            raise AssemblyError(
                f"{field} must be either a section or a page, not both"
            )
        unknown_keys = set(raw_node) - {"title", "children"}
        if unknown_keys:
            raise AssemblyError(
                f"{field} section contains unsupported fields: "
                + ", ".join(sorted(unknown_keys))
            )
        children = raw_node["children"]
        if not isinstance(children, list) or not children:
            raise AssemblyError(f"{field}.children must be a non-empty array")
        return Section(
            title=title,
            children=tuple(
                parse_navigation_node(child, f"{field}.children[{index}]")
                for index, child in enumerate(children)
            ),
            field=field,
        )

    unknown_keys = set(raw_node) - {"title", "source", "destination", "optional"}
    if unknown_keys:
        raise AssemblyError(
            f"{field} page contains unsupported fields: "
            + ", ".join(sorted(unknown_keys))
        )

    source_value = raw_node.get("source")
    destination_value = raw_node.get("destination")
    optional = raw_node.get("optional", False)
    if not isinstance(source_value, str) or not isinstance(destination_value, str):
        raise AssemblyError(f"{field} page source and destination must be strings")
    if not isinstance(optional, bool):
        raise AssemblyError(f"{field}.optional must be boolean")

    source = safe_relative_path(source_value, f"{field}.source")
    destination = safe_relative_path(destination_value, f"{field}.destination")
    if destination.suffix.lower() != ".md":
        raise AssemblyError(f"{field}.destination must be a Markdown file")
    return Page(
        title=title,
        source=source,
        destination=destination,
        optional=optional,
        field=field,
    )


def walk_nodes(nodes: tuple[NavigationNode, ...]):
    for node in nodes:
        yield node
        if isinstance(node, Section):
            yield from walk_nodes(node.children)


def load_manifest(path: Path) -> tuple[NavigationNode, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssemblyError(f"Unable to read manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("navigation"), list):
        raise AssemblyError("site-manifest.json must contain a navigation array")
    if not data["navigation"]:
        raise AssemblyError("site-manifest.json navigation must not be empty")

    nodes = tuple(
        parse_navigation_node(node, f"navigation[{index}]")
        for index, node in enumerate(data["navigation"])
    )

    titles: set[str] = set()
    sources: set[PurePosixPath] = set()
    destinations: set[PurePosixPath] = set()
    for node in walk_nodes(nodes):
        if node.title in titles:
            raise AssemblyError(f"Duplicate navigation title: {node.title}")
        titles.add(node.title)
        if not isinstance(node, Page):
            continue
        if node.source in sources:
            raise AssemblyError(f"Duplicate source: {node.source.as_posix()}")
        if node.destination in destinations:
            raise AssemblyError(
                f"Duplicate destination: {node.destination.as_posix()}"
            )
        sources.add(node.source)
        destinations.add(node.destination)

    return nodes


def toml_string(value: str) -> str:
    # JSON string syntax is compatible with TOML basic strings for these values.
    return json.dumps(value, ensure_ascii=False)


def render_nav(nodes: tuple[NavigationNode, ...], indent: int = 0) -> str:
    prefix = " " * indent
    entry_prefix = " " * (indent + 2)
    entries: list[str] = []
    for node in nodes:
        if isinstance(node, Page):
            entries.append(
                f"{entry_prefix}{{{toml_string(node.title)} = "
                f"{toml_string(node.destination.as_posix())}}}"
            )
        else:
            entries.append(
                f"{entry_prefix}{{{toml_string(node.title)} = "
                f"{render_nav(node.children, indent + 2)}}}"
            )
    return "[\n" + ",\n".join(entries) + f"\n{prefix}]"


def copy_directory_if_present(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def copy_canonical_assets(source: Path, destination: Path) -> None:
    """Copy non-Markdown assets without introducing unlisted pages."""
    if not source.is_dir():
        return
    for path in source.rglob("*"):
        if path.is_symlink():
            raise AssemblyError(f"Canonical assets must not contain symlinks: {path}")
        if not path.is_file() or path.suffix.lower() == ".md":
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def include_navigation(
    nodes: tuple[NavigationNode, ...],
    source_root: Path,
    docs_root: Path,
    skipped: list[str],
) -> tuple[NavigationNode, ...]:
    included: list[NavigationNode] = []
    for node in nodes:
        if isinstance(node, Section):
            children = include_navigation(node.children, source_root, docs_root, skipped)
            if children:
                included.append(
                    Section(title=node.title, children=children, field=node.field)
                )
            continue

        source_path = source_root.joinpath(*node.source.parts)
        if not source_path.is_file():
            if node.optional:
                skipped.append(node.source.as_posix())
                continue
            raise AssemblyError(f"Required source file does not exist: {source_path}")

        destination_path = docs_root.joinpath(*node.destination.parts)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        included.append(node)
    return tuple(included)


def count_pages(nodes: tuple[NavigationNode, ...]) -> int:
    return sum(1 for node in walk_nodes(nodes) if isinstance(node, Page))


def assemble(source_root: Path, site_root: Path, output_root: Path) -> list[str]:
    source_root = source_root.resolve(strict=True)
    site_root = site_root.resolve(strict=True)
    output_root = output_root.resolve()

    navigation = load_manifest(site_root / "site-manifest.json")
    template_path = site_root / "zensical.template.toml"
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssemblyError(f"Unable to read {template_path}: {exc}") from exc
    if template.count(NAV_PLACEHOLDER) != 1:
        raise AssemblyError(
            f"{template_path.name} must contain {NAV_PLACEHOLDER!r} exactly once"
        )

    if output_root.exists():
        shutil.rmtree(output_root)
    docs_root = output_root / "docs"
    docs_root.mkdir(parents=True)

    skipped: list[str] = []
    included = include_navigation(navigation, source_root, docs_root, skipped)
    if not included or not isinstance(included[0], Page):
        raise AssemblyError("The first included navigation entry must be a page")
    if included[0].destination != PurePosixPath("index.md"):
        raise AssemblyError("The first included page must generate index.md")

    copy_canonical_assets(source_root / "assets", docs_root / "assets")
    copy_directory_if_present(site_root / "assets", docs_root)

    config = template.replace(NAV_PLACEHOLDER, render_nav(included))
    (output_root / "zensical.toml").write_text(config, encoding="utf-8")

    summary = [
        f"assembled {count_pages(included)} page(s)",
        f"output: {output_root}",
    ]
    if skipped:
        summary.append("optional pages skipped: " + ", ".join(skipped))
    return summary


def main() -> int:
    args = parse_args()
    try:
        summary = assemble(args.source_root, args.site_root, args.output_root)
    except (AssemblyError, OSError) as exc:
        print(f"assemble_docs.py: {exc}", file=sys.stderr)
        return 1
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
