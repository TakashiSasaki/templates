#!/usr/bin/env python3
"""Prepare the site publication with generated repository-tree page declarations."""

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
        "id": "repository-tree-skill",
        "source": "docs/repository-trees/skill.md",
        "optional": False,
        "home": False,
    },
    {
        "id": "repository-tree-policy",
        "source": "docs/repository-trees/policy.md",
        "optional": False,
        "home": False,
    },
    {
        "id": "repository-tree-webapp",
        "source": "docs/repository-trees/webapp.md",
        "optional": False,
        "home": False,
    },
)
WEBAPP_TEMPLATE_DOCUMENT = {
    "id": "repository-tree-webapp-template",
    "source": "docs/repository-trees/webapp/template.md",
    "optional": False,
    "home": False,
}
SKILL_TEMPLATE_DOCUMENT = {
    "id": "repository-tree-skill-template",
    "source": "docs/repository-trees/skill/template.md",
    "optional": False,
    "home": False,
}
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
            "title": "Skill tree",
            "publication": "site",
            "document": "repository-tree-skill",
            "destination": "repository-trees/skill.md",
        },
        {
            "title": "Policy tree",
            "publication": "site",
            "document": "repository-tree-policy",
            "destination": "repository-trees/policy.md",
        },
        {
            "title": "Web application tree",
            "publication": "site",
            "document": "repository-tree-webapp",
            "destination": "repository-trees/webapp.md",
        },
    ],
}
WEBAPP_TEMPLATE_NAVIGATION = {
    "title": "Web application copyable template",
    "publication": "site",
    "document": "repository-tree-webapp-template",
    "destination": "repository-trees/webapp/template.md",
}
SKILL_TEMPLATE_NAVIGATION = {
    "title": "Skill copyable template",
    "publication": "site",
    "document": "repository-tree-skill-template",
    "destination": "repository-trees/skill/template.md",
}


class PreparationError(RuntimeError):
    """Raised when the generated site publication cannot be prepared safely."""


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
    generated_documents: Iterable[dict[str, Any]] = (*TREE_DOCUMENTS, WEBAPP_TEMPLATE_DOCUMENT),
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


def augment_manifest(
    manifest: dict[str, Any],
    template_navigation: Iterable[dict[str, Any]] = (WEBAPP_TEMPLATE_NAVIGATION,),
) -> dict[str, Any]:
    navigation = manifest.get("navigation")
    if not isinstance(navigation, list) or not navigation:
        raise PreparationError("site manifest navigation must be a non-empty array")
    template_navigation = tuple(template_navigation)
    generated_titles = {
        TREE_NAVIGATION["title"],
        *(entry["title"] for entry in template_navigation),
    }
    if any(
        isinstance(node, dict) and node.get("title") in generated_titles
        for node in navigation
    ):
        raise PreparationError(
            "base site manifest must not predeclare generated repository trees"
        )

    result = dict(manifest)
    result["navigation"] = [
        navigation[0],
        json.loads(json.dumps(TREE_NAVIGATION)),
        *(json.loads(json.dumps(entry)) for entry in template_navigation),
        *navigation[1:],
    ]
    return result


def generated_template_contracts(
    output_root: Path,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    documents = [*TREE_DOCUMENTS, WEBAPP_TEMPLATE_DOCUMENT]
    navigation = [WEBAPP_TEMPLATE_NAVIGATION]
    skill_template = output_root / SKILL_TEMPLATE_DOCUMENT["source"]
    if skill_template.is_symlink():
        raise PreparationError(
            f"repository-tree template must not be a symlink: {skill_template}"
        )
    if skill_template.is_file():
        documents.append(SKILL_TEMPLATE_DOCUMENT)
        navigation.append(SKILL_TEMPLATE_NAVIGATION)
    return tuple(documents), tuple(navigation)


def prepare(site_root: Path, output_root: Path) -> list[str]:
    site_root = site_root.resolve(strict=True)

    manifest_path = site_root / "site-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PreparationError(
            f"site manifest must be a regular file: {manifest_path}"
        )

    output_root = prepare_output_root(output_root, site_root)

    docs_source = site_root / "docs"
    copy_tree(docs_source, output_root / "docs", "site docs")

    assets_source = site_root / "assets"
    if assets_source.exists():
        copy_tree(assets_source, output_root / "assets", "site assets")

    template_source = site_root / "zensical.template.toml"
    if template_source.is_symlink() or not template_source.is_file():
        raise PreparationError(
            f"site template must be a regular file: {template_source}"
        )
    shutil.copy2(template_source, output_root / template_source.name)

    generated_documents, template_navigation = generated_template_contracts(output_root)
    catalog_path = output_root / "docs/publication-catalog.json"
    prepared_manifest_path = output_root / "site-manifest.json"

    write_json(
        catalog_path,
        augment_catalog(
            read_json(catalog_path, "site publication catalog"),
            generated_documents,
        ),
    )
    write_json(
        prepared_manifest_path,
        augment_manifest(
            read_json(manifest_path, "site manifest"),
            template_navigation,
        ),
    )

    for document in generated_documents:
        template = output_root / document["source"]
        if not template.is_file():
            raise PreparationError(
                f"repository-tree template is missing: {template}"
            )

    return [
        f"prepared site publication: {output_root.resolve()}",
        f"generated documents: {len(generated_documents)}",
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
