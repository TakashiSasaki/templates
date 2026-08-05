#!/usr/bin/env python3
"""Assemble branch-owned publication catalogs into one Zensical project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

NAV_PLACEHOLDER = "__GENERATED_NAV__"
NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class AssemblyError(RuntimeError):
    """Raised when publication assembly inputs or outputs are invalid."""


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssemblyError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AssemblyError(f"{label} contains duplicate member: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise AssemblyError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AssemblyError(f"{label} must be an object")
    return value


def safe_path(value: Any, field: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
    ):
        raise AssemblyError(f"{field} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(
        part in ("", ".", "..") or part.casefold() == ".git"
        for part in parts
    ):
        raise AssemblyError(f"{field} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise AssemblyError(f"{field} must be a safe relative POSIX path")
    return path


def parse_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise AssemblyError(f"{field} must be lowercase kebab-case")
    return value


def resolve(root: Path, relative: PurePosixPath, field: str) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise AssemblyError(
                f"{field} must remain within publication root: {relative}"
            ) from exc
        if current.is_symlink():
            raise AssemblyError(f"{field} must not traverse a symlink: {relative}")
    return current


def paths_overlap(first: PurePosixPath, second: PurePosixPath) -> bool:
    return first == second or first in second.parents or second in first.parents


def reject_overlapping_paths(
    paths: list[PurePosixPath],
    description: str,
) -> None:
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            if paths_overlap(first, second):
                raise AssemblyError(
                    f"{description} must not overlap: {first} and {second}"
                )


def load_catalog(
    name: str,
    root: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    catalog_path = resolve(
        root,
        PurePosixPath("docs/publication-catalog.json"),
        f"{name} catalog",
    )
    data = read_json(catalog_path, f"{name} catalog")
    version = data.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise AssemblyError(
            f"{name} catalog schema_version must be integer 1 or 2"
        )

    allowed = {"schema_version", "documents"}
    if version == 2:
        allowed.add("assets")
    unknown = set(data) - allowed
    if unknown:
        raise AssemblyError(
            f"{name} catalog has unsupported fields: "
            + ", ".join(sorted(unknown))
        )

    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise AssemblyError(
            f"{name} catalog documents must be a non-empty array"
        )

    documents: dict[str, dict[str, Any]] = {}
    document_sources: set[PurePosixPath] = set()
    homes = 0
    for index, raw in enumerate(raw_documents):
        field = f"{name}.documents[{index}]"
        if (
            not isinstance(raw, dict)
            or set(raw) != {"id", "source", "optional", "home"}
        ):
            raise AssemblyError(
                f"{field} must contain id, source, optional, and home"
            )
        document_id = parse_name(raw["id"], f"{field}.id")
        source = safe_path(raw["source"], f"{field}.source")
        if source.suffix.lower() != ".md":
            raise AssemblyError(f"{field}.source must be Markdown")
        if not isinstance(raw["optional"], bool) or not isinstance(raw["home"], bool):
            raise AssemblyError(f"{field}.optional and home must be boolean")
        if document_id in documents or source in document_sources:
            raise AssemblyError(
                f"{name} catalog document IDs and sources must be unique"
            )
        if raw["home"]:
            homes += 1
            if raw["optional"]:
                raise AssemblyError(f"{name} catalog home must not be optional")
        documents[document_id] = {
            "source": source,
            "optional": raw["optional"],
            "home": raw["home"],
        }
        document_sources.add(source)

    if homes != 1:
        raise AssemblyError(f"{name} catalog must define exactly one home")

    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise AssemblyError(f"{name} catalog assets must be an array")

    assets: list[dict[str, Any]] = []
    asset_sources: list[PurePosixPath] = []
    asset_destinations: list[PurePosixPath] = []
    for index, raw in enumerate(raw_assets):
        field = f"{name}.assets[{index}]"
        if (
            not isinstance(raw, dict)
            or set(raw) != {"source", "destination", "optional"}
        ):
            raise AssemblyError(
                f"{field} must contain source, destination, and optional"
            )
        source = safe_path(raw["source"], f"{field}.source")
        destination = safe_path(raw["destination"], f"{field}.destination")
        if not isinstance(raw["optional"], bool):
            raise AssemblyError(f"{field}.optional must be boolean")
        asset_sources.append(source)
        asset_destinations.append(destination)
        assets.append(
            {
                "source": source,
                "destination": destination,
                "optional": raw["optional"],
            }
        )

    if len(set(asset_sources)) != len(asset_sources):
        raise AssemblyError(f"{name} catalog asset sources must be unique")
    reject_overlapping_paths(
        asset_sources,
        f"{name} catalog asset sources",
    )
    if len(set(asset_destinations)) != len(asset_destinations):
        raise AssemblyError(f"{name} catalog asset destinations must be unique")
    reject_overlapping_paths(
        asset_destinations,
        f"{name} catalog asset destinations",
    )
    return documents, assets


def parse_node(raw: Any, field: str) -> dict[str, Any]:
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("title"), str)
        or not raw["title"].strip()
    ):
        raise AssemblyError(f"{field} must have a non-empty title")
    if "children" in raw:
        if (
            set(raw) != {"title", "children"}
            or not isinstance(raw["children"], list)
            or not raw["children"]
        ):
            raise AssemblyError(
                f"{field} section must contain only title and non-empty children"
            )
        return {
            "title": raw["title"].strip(),
            "children": [
                parse_node(value, f"{field}.children[{index}]")
                for index, value in enumerate(raw["children"])
            ],
        }
    if set(raw) != {"title", "publication", "document", "destination"}:
        raise AssemblyError(
            f"{field} page must contain title, publication, document, and destination"
        )
    return {
        "title": raw["title"].strip(),
        "publication": parse_name(raw["publication"], f"{field}.publication"),
        "document": parse_name(raw["document"], f"{field}.document"),
        "destination": safe_path(raw["destination"], f"{field}.destination"),
    }


def pages(nodes: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for node in nodes:
        if "children" in node:
            yield from pages(node["children"])
        else:
            yield node


def load_manifest(
    path: Path,
) -> tuple[tuple[str, str], list[dict[str, Any]]]:
    data = read_json(path, "site manifest")
    if (
        set(data) != {"schema_version", "home", "navigation"}
        or data.get("schema_version") != 2
    ):
        raise AssemblyError(
            "site manifest must be schema version 2 with home and navigation"
        )
    home = data["home"]
    if not isinstance(home, dict) or set(home) != {"publication", "document"}:
        raise AssemblyError(
            "site manifest home must identify publication and document"
        )
    navigation = data["navigation"]
    if not isinstance(navigation, list) or not navigation:
        raise AssemblyError("site manifest navigation must be non-empty")
    return (
        (
            parse_name(home["publication"], "home.publication"),
            parse_name(home["document"], "home.document"),
        ),
        [
            parse_node(value, f"navigation[{index}]")
            for index, value in enumerate(navigation)
        ],
    )


def copy_asset(
    source: Path,
    destination: Path,
    field: str,
    *,
    skip_markdown: bool = False,
) -> None:
    if source.is_symlink():
        raise AssemblyError(f"{field} must not be a symlink")
    entries = (
        [source]
        if source.is_file()
        else list(source.rglob("*"))
        if source.is_dir()
        else []
    )
    if not entries:
        raise AssemblyError(f"{field} does not exist or is empty: {source}")

    for item in entries:
        relative_item = Path() if source.is_file() else item.relative_to(source)
        if any(part.casefold() == ".git" for part in relative_item.parts):
            raise AssemblyError(f"{field} contains a .git subtree: {item}")
        if item.is_symlink():
            raise AssemblyError(f"{field} contains a symlink: {item}")
        if not item.is_file():
            continue
        target = destination if source.is_file() else destination / relative_item
        if item.suffix.lower() == ".md" or target.suffix.lower() == ".md":
            if skip_markdown:
                continue
            raise AssemblyError(
                f"{field} would publish undeclared Markdown: {target}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise AssemblyError(f"output collision: {target}")
        shutil.copy2(item, target)


def render_nav(nodes: list[dict[str, Any]], indent: int = 0) -> str:
    prefix = " " * indent
    entry = " " * (indent + 2)
    values = []
    for node in nodes:
        title = json.dumps(node["title"], ensure_ascii=False)
        if "children" in node:
            values.append(
                f"{entry}{{{title} = {render_nav(node['children'], indent + 2)}}}"
            )
        else:
            destination = json.dumps(
                node["destination"].as_posix(),
                ensure_ascii=False,
            )
            values.append(f"{entry}{{{title} = {destination}}}")
    return "[\n" + ",\n".join(values) + f"\n{prefix}]"


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

    home, navigation = load_manifest(site_root / "site-manifest.json")
    navigation_pages = list(pages(navigation))
    seen: set[tuple[str, str]] = set()
    destinations: set[PurePosixPath] = set()
    for page in navigation_pages:
        key = (page["publication"], page["document"])
        if key in seen or page["destination"] in destinations:
            raise AssemblyError(
                "site manifest document keys and destinations must be unique"
            )
        seen.add(key)
        destinations.add(page["destination"])
        if (
            key[0] not in publications
            or key[1] not in publications[key[0]][1]
        ):
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
        not navigation_pages
        or (
            navigation_pages[0]["publication"],
            navigation_pages[0]["document"],
        )
        != home
        or navigation_pages[0]["destination"] != PurePosixPath("index.md")
    ):
        raise AssemblyError("site home page must generate index.md")
    home_document = publications[home[0]][1][home[1]]
    if not home_document["home"]:
        raise AssemblyError("global home must be the selected publication home")

    if output_root.is_symlink():
        raise AssemblyError("output root must not be a symlink")
    if output_root.exists():
        shutil.rmtree(output_root)
    docs_root = output_root / "docs"
    docs_root.mkdir(parents=True)

    included: list[dict[str, Any]] = []
    skipped: set[tuple[str, str]] = set()
    for page in navigation_pages:
        root, documents, _ = publications[page["publication"]]
        document = documents[page["document"]]
        source = resolve(
            root,
            document["source"],
            f"{page['publication']}:{page['document']}",
        )
        if not source.is_file():
            if document["optional"] and not source.exists():
                skipped.add((page["publication"], page["document"]))
                continue
            raise AssemblyError(
                f"required publication document does not exist: {source}"
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
            elif (
                node["publication"],
                node["document"],
            ) not in skipped:
                result.append(node)
        return result

    filtered_navigation = filter_nodes(navigation)
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

        # Catalog v1 predates explicit asset roots. Preserve its established
        # convention for non-Markdown files only. Markdown remains catalog-only
        # and is omitted rather than becoming an implicit page or build failure.
        legacy_assets = root / "assets"
        if name != "site" and not assets and legacy_assets.is_dir():
            copy_asset(
                legacy_assets,
                docs_root / name / "assets",
                f"{name} legacy assets",
                skip_markdown=True,
            )

    site_assets = site_root / "assets"
    if site_assets.is_dir():
        copy_asset(site_assets, docs_root, "site assets")

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


def parse_publications(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for index, value in enumerate(values):
        if "=" not in value:
            raise AssemblyError(
                f"--publication[{index}] must use NAME=PATH"
            )
        name, raw_path = value.split("=", 1)
        name = parse_name(name, f"--publication[{index}].name")
        if not raw_path or name in result:
            raise AssemblyError(
                f"invalid or duplicate publication: {value!r}"
            )
        result[name] = Path(raw_path)
    if not result:
        raise AssemblyError("at least one --publication is required")
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
