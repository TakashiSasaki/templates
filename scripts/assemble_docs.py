#!/usr/bin/env python3
"""Assemble canonical documentation into a temporary Zensical project."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

NAV_PLACEHOLDER = "__GENERATED_NAV__"


class AssemblyError(RuntimeError):
    """Raised when the site manifest or source tree is invalid."""


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


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssemblyError(f"Unable to read manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise AssemblyError("site-manifest.json must contain a pages array")
    return data


def toml_string(value: str) -> str:
    # JSON string syntax is compatible with TOML basic strings for these values.
    return json.dumps(value, ensure_ascii=False)


def render_nav(pages: list[tuple[str, PurePosixPath]]) -> str:
    entries = [
        f"  {{{toml_string(title)} = {toml_string(destination.as_posix())}}}"
        for title, destination in pages
    ]
    return "[\n" + ",\n".join(entries) + "\n]"


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


def assemble(source_root: Path, site_root: Path, output_root: Path) -> list[str]:
    source_root = source_root.resolve(strict=True)
    site_root = site_root.resolve(strict=True)
    output_root = output_root.resolve()

    manifest = load_manifest(site_root / "site-manifest.json")
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

    included: list[tuple[str, PurePosixPath]] = []
    seen_destinations: set[PurePosixPath] = set()
    skipped: list[str] = []

    for index, raw_page in enumerate(manifest["pages"]):
        if not isinstance(raw_page, dict):
            raise AssemblyError(f"pages[{index}] must be an object")
        title = raw_page.get("title")
        source_value = raw_page.get("source")
        destination_value = raw_page.get("destination")
        optional = raw_page.get("optional", False)
        if not isinstance(title, str) or not title.strip():
            raise AssemblyError(f"pages[{index}].title must be a non-empty string")
        if not isinstance(source_value, str) or not isinstance(destination_value, str):
            raise AssemblyError(
                f"pages[{index}] source and destination must be strings"
            )
        if not isinstance(optional, bool):
            raise AssemblyError(f"pages[{index}].optional must be boolean")

        source_relative = safe_relative_path(source_value, f"pages[{index}].source")
        destination_relative = safe_relative_path(
            destination_value, f"pages[{index}].destination"
        )
        if destination_relative.suffix.lower() != ".md":
            raise AssemblyError(
                f"pages[{index}].destination must be a Markdown file"
            )
        if destination_relative in seen_destinations:
            raise AssemblyError(
                f"Duplicate destination: {destination_relative.as_posix()}"
            )

        source_path = source_root.joinpath(*source_relative.parts)
        if not source_path.is_file():
            if optional:
                skipped.append(source_relative.as_posix())
                continue
            raise AssemblyError(f"Required source file does not exist: {source_path}")

        destination_path = docs_root.joinpath(*destination_relative.parts)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        seen_destinations.add(destination_relative)
        included.append((title.strip(), destination_relative))

    if not included or included[0][1] != PurePosixPath("index.md"):
        raise AssemblyError("The first included page must generate index.md")

    copy_canonical_assets(source_root / "assets", docs_root / "assets")
    copy_directory_if_present(site_root / "assets", docs_root)

    config = template.replace(NAV_PLACEHOLDER, render_nav(included))
    (output_root / "zensical.toml").write_text(config, encoding="utf-8")

    summary = [
        f"assembled {len(included)} page(s)",
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
