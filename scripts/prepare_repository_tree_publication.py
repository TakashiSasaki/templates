#!/usr/bin/env python3
"""Prepare the Site publication with Composition/Policy repository-tree pages."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

OUTPUT_MARKER = ".repository-tree-publication-root"
OUTPUT_MARKER_CONTENT = "managed by scripts/prepare_repository_tree_publication.py\n"
TREE_DOCUMENTS = (
    {
        "id": "repository-trees",
        "source": "docs/repository-trees/overview.md",
        "optional": False,
        "home": False,
    },
    {
        "id": "repository-tree-composition",
        "source": "docs/repository-trees/composition.md",
        "optional": False,
        "home": False,
    },
    {
        "id": "repository-tree-policy",
        "source": "docs/repository-trees/policy.md",
        "optional": False,
        "home": False,
    },
)
TREE_NAVIGATION = {
    "title": "Repository trees",
    "children": [
        {
            "title": "Overview",
            "publication": "site",
            "document": "repository-trees",
            "destination": "repository-trees/index.md",
        },
        {
            "title": "Composition tree",
            "publication": "site",
            "document": "repository-tree-composition",
            "destination": "repository-trees/composition.md",
        },
        {
            "title": "Policy tree",
            "publication": "site",
            "document": "repository-tree-policy",
            "destination": "repository-trees/policy.md",
        },
    ],
}


class PreparationError(RuntimeError):
    """Raised when generated Site publication cannot be prepared safely."""


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreparationError(f"unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreparationError(f"{label} must be an object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def prepare_output_root(output_root: Path, site_root: Path) -> Path:
    if output_root.is_symlink():
        raise PreparationError("output root must not be a symlink")
    resolved_output = output_root.resolve(strict=False)
    resolved_site = site_root.resolve(strict=True)
    if resolved_output.parent == resolved_output:
        raise PreparationError("output root must not be a filesystem root")
    if paths_overlap(resolved_output, resolved_site):
        raise PreparationError("output root must not overlap the site source")

    if output_root.exists():
        if not output_root.is_dir():
            raise PreparationError("output root must be a directory")
        entries = list(output_root.iterdir())
        if entries:
            marker = output_root / OUTPUT_MARKER
            if marker.is_symlink() or not marker.is_file():
                raise PreparationError(
                    "existing output root is not managed by repository-tree preparation"
                )
            try:
                marker_content = marker.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise PreparationError(
                    f"unable to verify output marker {marker}: {exc}"
                ) from exc
            if marker_content != OUTPUT_MARKER_CONTENT:
                raise PreparationError(
                    "existing output root is not managed by repository-tree preparation"
                )
            shutil.rmtree(output_root)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / OUTPUT_MARKER).write_text(
        OUTPUT_MARKER_CONTENT,
        encoding="utf-8",
    )
    return output_root


def copy_tree(source: Path, destination: Path, label: str) -> None:
    if source.is_symlink():
        raise PreparationError(f"{label} must not be a symlink")
    if not source.is_dir():
        raise PreparationError(f"{label} must be a directory: {source}")
    destination.mkdir(parents=True, exist_ok=True)

    pending = [(source, destination)]
    while pending:
        current_source, current_destination = pending.pop()
        try:
            children = sorted(current_source.iterdir(), key=lambda child: child.name)
        except OSError as exc:
            raise PreparationError(
                f"unable to inspect {label} {current_source}: {exc}"
            ) from exc
        for child in children:
            if child.is_symlink():
                raise PreparationError(f"{label} contains a symlink: {child}")
            target = current_destination / child.name
            if child.is_dir():
                target.mkdir()
                pending.append((child, target))
            elif child.is_file():
                shutil.copy2(child, target)
            else:
                raise PreparationError(
                    f"{label} contains an unsupported entry: {child}"
                )


def augment_catalog(
    catalog: dict[str, Any],
    generated_documents: Iterable[dict[str, Any]] = TREE_DOCUMENTS,
) -> dict[str, Any]:
    documents = catalog.get("documents")
    if not isinstance(documents, list):
        raise PreparationError("site publication catalog documents must be an array")
    existing_ids: set[str] = set()
    existing_sources: set[str] = set()
    for document in documents:
        if not isinstance(document, dict):
            raise PreparationError("site publication catalog documents must be objects")
        identifier = document.get("id")
        source = document.get("source")
        if not isinstance(identifier, str) or not isinstance(source, str):
            raise PreparationError("site publication catalog document is invalid")
        existing_ids.add(identifier)
        existing_sources.add(source)

    additions = []
    for document in generated_documents:
        if document["id"] in existing_ids or document["source"] in existing_sources:
            raise PreparationError(
                "base site publication must not predeclare generated repository trees"
            )
        additions.append(dict(document))

    result = dict(catalog)
    result["documents"] = [*documents, *additions]
    return result


def augment_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    navigation = manifest.get("navigation")
    if not isinstance(navigation, list) or not navigation:
        raise PreparationError("site manifest navigation must be a non-empty array")
    if any(
        isinstance(node, dict) and node.get("title") == TREE_NAVIGATION["title"]
        for node in navigation
    ):
        raise PreparationError(
            "base site manifest must not predeclare generated repository trees"
        )

    result = dict(manifest)
    result["navigation"] = [
        navigation[0],
        json.loads(json.dumps(TREE_NAVIGATION)),
        *navigation[1:],
    ]
    return result


def prepare(site_root: Path, output_root: Path) -> list[str]:
    site_root = site_root.resolve(strict=True)
    manifest_path = site_root / "site-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PreparationError(
            f"site manifest must be a regular file: {manifest_path}"
        )

    output_root = prepare_output_root(output_root, site_root)
    copy_tree(site_root / "docs", output_root / "docs", "site docs")

    assets_source = site_root / "assets"
    if assets_source.exists():
        copy_tree(assets_source, output_root / "assets", "site assets")

    translations_source = site_root / "translations"
    if translations_source.exists():
        copy_tree(
            translations_source,
            output_root / "translations",
            "site translations",
        )

    template_source = site_root / "zensical.template.toml"
    if template_source.is_symlink() or not template_source.is_file():
        raise PreparationError(
            f"site template must be a regular file: {template_source}"
        )
    shutil.copy2(template_source, output_root / template_source.name)

    catalog_path = output_root / "docs/publication-catalog.json"
    prepared_manifest_path = output_root / "site-manifest.json"
    write_json(
        catalog_path,
        augment_catalog(read_json(catalog_path, "site publication catalog")),
    )
    write_json(
        prepared_manifest_path,
        augment_manifest(read_json(manifest_path, "site manifest")),
    )

    for document in TREE_DOCUMENTS:
        template = output_root / document["source"]
        if not template.is_file():
            raise PreparationError(
                f"repository-tree template is missing: {template}"
            )

    return [
        f"prepared site publication: {output_root.resolve()}",
        f"generated documents: {len(TREE_DOCUMENTS)}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    try:
        messages = prepare(site_root=args.site_root, output_root=args.output_root)
    except PreparationError as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())