#!/usr/bin/env python3
"""Assemble branch-owned publication catalogs into one Zensical project."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.materialize_publication_assets import (
    PublicationMaterializationError,
    load_materialized_publication_catalog,
)
from scripts.publication_contract import (
    PublicationContractError,
    parse_name as contract_parse_name,
    resolve_without_symlinks,
    safe_relative_path,
)

NAV_PLACEHOLDER = "__GENERATED_NAV__"
OUTPUT_MARKER = ".publication-assembly-root"
OUTPUT_MARKER_CONTENT = "managed by scripts/assemble_publications.py\n"


from integration.publication_model import (
    AssemblyError,
    read_json,
    safe_path,
    parse_name,
    resolve,
    load_catalog,
    parse_node,
    Manifest,
    pages,
    parse_manifest,
    load_manifest,
    asset_entries,
    copy_asset,
    parse_publications,
)














from integration.publication_model import AUDIENCE_TITLES














from site_renderer.config import (
    render_nav,
)


def real_paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def prepare_output_root(output_root: Path, protected_roots: list[Path]) -> Path:
    """Create or safely replace a tool-owned assembly directory."""
    if output_root.is_symlink():
        raise AssemblyError("output root must not be a symlink")

    resolved_output = output_root.resolve(strict=False)
    if resolved_output.parent == resolved_output:
        raise AssemblyError("output root must not be a filesystem root")

    current_directory = Path.cwd().resolve(strict=True)
    if resolved_output == current_directory or resolved_output in current_directory.parents:
        raise AssemblyError(
            "output root must not be the current working directory or its ancestor"
        )

    for protected_root in protected_roots:
        resolved_protected = protected_root.resolve(strict=True)
        if real_paths_overlap(resolved_output, resolved_protected):
            raise AssemblyError(
                f"output root must not overlap publication root: {resolved_protected}"
            )

    if output_root.exists():
        if not output_root.is_dir():
            raise AssemblyError("output root must be a directory")
        entries = list(output_root.iterdir())
        if entries:
            marker = output_root / OUTPUT_MARKER
            if marker.is_symlink() or not marker.is_file():
                raise AssemblyError(
                    "existing output root is not managed by publication assembly"
                )
            try:
                marker_content = marker.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise AssemblyError(
                    f"unable to verify output root marker {marker}: {exc}"
                ) from exc
            if marker_content != OUTPUT_MARKER_CONTENT:
                raise AssemblyError(
                    "existing output root is not managed by publication assembly"
                )
            shutil.rmtree(output_root)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / OUTPUT_MARKER).write_text(
        OUTPUT_MARKER_CONTENT,
        encoding="utf-8",
    )
    return output_root


def assemble(
    publication_roots: dict[str, Path],
    site_root: Path,
    output_root: Path,
) -> list[str]:
    site_root = site_root.resolve(strict=True)
    publications: dict[
        str,
        tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]],
    ] = {}
    for name, root in sorted(publication_roots.items()):
        resolved_root = root.resolve(strict=True)
        documents, assets = load_catalog(name, resolved_root)
        publications[name] = (resolved_root, documents, assets)

    manifest = load_manifest(site_root / "site-manifest.json")
    home = manifest.home
    canonical_documents = manifest.documents
    seen: set[tuple[str, str]] = set()
    destinations: set[PurePosixPath] = set()
    for page in canonical_documents:
        key = (page["publication"], page["document"])
        if key in seen or page["destination"] in destinations:
            raise AssemblyError(
                "site manifest document keys and destinations must be unique"
            )
        seen.add(key)
        destinations.add(page["destination"])
        if key[0] not in publications or key[1] not in publications[key[0]][1]:
            raise AssemblyError(
                f"site manifest references unknown document: {key[0]}:{key[1]}"
            )

    catalog_keys = {
        (name, document_id)
        for name, (_, documents, _) in publications.items()
        for document_id in documents
    }
    if seen != catalog_keys:
        missing = sorted(catalog_keys - seen)
        extra = sorted(seen - catalog_keys)
        if missing:
            detail = ", ".join(
                f"{publication}:{document}"
                for publication, document in missing
            )
            raise AssemblyError(
                "site manifest does not cover publication documents: " + detail
            )
        detail = ", ".join(
            f"{publication}:{document}"
            for publication, document in extra
        )
        raise AssemblyError(
            "site manifest references extra publication documents: " + detail
        )

    if (
        not canonical_documents
        or (
            canonical_documents[0]["publication"],
            canonical_documents[0]["document"],
        )
        != home
        or canonical_documents[0]["destination"] != PurePosixPath("index.md")
    ):
        raise AssemblyError("site home page must generate index.md")
    home_document = publications[home[0]][1][home[1]]
    if not home_document["home"]:
        raise AssemblyError("global home must be the selected publication home")

    output_root = prepare_output_root(
        output_root,
        [site_root, *(root for root, _, _ in publications.values())],
    )
    docs_root = output_root / "docs"
    docs_root.mkdir(parents=True)

    included: list[dict[str, Any]] = []
    skipped: set[tuple[str, str]] = set()
    for page in canonical_documents:
        root, documents, _ = publications[page["publication"]]
        document = documents[page["document"]]
        source = resolve(
            root,
            document["source"],
            f"{page['publication']}:{page['document']}",
        )
        if not source.is_file():
            if not source.exists():
                if document["optional"]:
                    skipped.add((page["publication"], page["document"]))
                    continue
                raise AssemblyError(
                    f"required publication document does not exist: {source}"
                )
            raise AssemblyError(
                f"publication document must be a regular file: {source}"
            )
        target = docs_root.joinpath(*page["destination"].parts)
        try:
            target.relative_to(docs_root)
        except ValueError as exc:
            raise AssemblyError(
                f"document destination escapes output root: {page['destination']}"
            ) from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise AssemblyError(f"output collision: {target}")
        shutil.copy2(source, target)
        included.append(page)

    def filter_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for node in nodes:
            if "children" in node:
                children = filter_nodes(node["children"])
                if children:
                    result.append(
                        {"title": node["title"], "children": children}
                    )
            elif (node["publication"], node["document"]) not in skipped:
                result.append(node)
        return result

    if manifest.schema_version == 3:
        filtered_nav_dict = {
            audience: filter_nodes(manifest.navigation[audience])
            for audience in manifest.audiences
        }
        filtered_navigation = [
            {
                "title": AUDIENCE_TITLES.get(audience, audience),
                "children": filtered_nav_dict[audience],
            }
            for audience in manifest.audiences
            if filtered_nav_dict[audience]
        ]
    else:
        filtered_navigation = filter_nodes(manifest.navigation)
    for name, (root, _, assets) in publications.items():
        for asset in assets:
            source = resolve(root, asset["source"], f"{name} asset")
            if not source.exists() and asset["optional"]:
                continue
            destination = docs_root / name / asset["destination"]
            try:
                destination.relative_to(docs_root)
            except ValueError as exc:
                raise AssemblyError(
                    f"{name} asset destination escapes output root: "
                    f"{asset['destination']}"
                ) from exc
            copy_asset(source, destination, f"{name} asset")

    site_assets = site_root / "assets"
    if site_assets.is_dir():
        copy_asset(site_assets, docs_root, "site assets")

    if manifest.schema_version == 3:
        try:
            from scripts.audience_context import AudienceContextResolver
        except ImportError:
            from audience_context import AudienceContextResolver
        # Optional documents absent from the selected publication are not part
        # of the built site and must not acquire audience metadata on their 404s.
        resolver = AudienceContextResolver(manifest, documents=included)
        (docs_root / "audience-runtime.json").write_text(
            json.dumps(resolver.export_runtime_map(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    template_path = site_root / "zensical.template.toml"
    template = template_path.read_text(encoding="utf-8")
    if template.count(NAV_PLACEHOLDER) != 1:
        raise AssemblyError(
            f"{template_path.name} must contain {NAV_PLACEHOLDER!r} exactly once"
        )
    (output_root / "zensical.toml").write_text(
        template.replace(
            NAV_PLACEHOLDER,
            render_nav(filtered_navigation),
        ),
        encoding="utf-8",
    )

    result = [
        f"assembled {len(included)} page(s)",
        f"publications: {len(publications)}",
        f"catalog documents: {len(catalog_keys)}",
        f"output: {output_root.resolve()}",
    ]
    if skipped:
        result.append(
            "optional documents skipped: "
            + ", ".join(
                f"{publication}:{document}"
                for publication, document in sorted(skipped)
            )
        )
    return result




def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", action="append", default=[])
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(
            "\n".join(
                assemble(
                    parse_publications(args.publication),
                    args.site_root,
                    args.output_root,
                )
            )
        )
    except (AssemblyError, OSError) as exc:
        print(f"assemble_publications.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
