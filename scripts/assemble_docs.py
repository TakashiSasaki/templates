#!/usr/bin/env python3
"""Assemble canonical documentation into a temporary Zensical project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, TypeAlias

NAV_PLACEHOLDER = "__GENERATED_NAV__"
DOCUMENT_ID_PATTERN = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class AssemblyError(RuntimeError):
    """Raised when the publication catalog, site manifest, or source tree is invalid."""


@dataclass(frozen=True)
class PublicationDocument:
    document_id: str
    source: PurePosixPath
    optional: bool
    home: bool
    field: str


@dataclass(frozen=True)
class Page:
    title: str
    document_id: str
    destination: PurePosixPath
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


def read_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AssemblyError(f"Unable to read {description} {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssemblyError(f"{description} must be valid UTF-8: {path}") from exc

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AssemblyError(
                    f"{description} contains duplicate object member: {key}"
                )
            result[key] = value
        return result

    try:
        data = json.loads(text, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise AssemblyError(f"Unable to parse {description} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AssemblyError(f"{description} must be a JSON object")
    return data


def safe_relative_path(value: str, field: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise AssemblyError(f"{field} must be a safe non-empty relative path: {value!r}")
    raw_parts = value.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        raise AssemblyError(f"{field} must be a safe non-empty relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise AssemblyError(f"{field} must be a safe non-empty relative path: {value!r}")
    return path


def parse_document_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DOCUMENT_ID_PATTERN.fullmatch(value):
        raise AssemblyError(f"{field} must be a lowercase kebab-case document ID")
    return value


def load_publication_catalog(path: Path) -> tuple[PublicationDocument, ...]:
    data = read_json_object(path, "publication catalog")
    unknown_top_level = set(data) - {"schema_version", "documents"}
    if unknown_top_level:
        raise AssemblyError(
            "publication catalog contains unsupported top-level fields: "
            + ", ".join(sorted(unknown_top_level))
        )
    schema_version = data.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise AssemblyError("publication catalog schema_version must be the integer 1")
    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise AssemblyError("publication catalog documents must be a non-empty array")

    documents: list[PublicationDocument] = []
    document_ids: set[str] = set()
    sources: set[PurePosixPath] = set()
    for index, raw_document in enumerate(raw_documents):
        field = f"documents[{index}]"
        if not isinstance(raw_document, dict):
            raise AssemblyError(f"{field} must be an object")
        unknown_fields = set(raw_document) - {"id", "source", "optional", "home"}
        if unknown_fields:
            raise AssemblyError(
                f"{field} contains unsupported fields: "
                + ", ".join(sorted(unknown_fields))
            )
        if set(raw_document) != {"id", "source", "optional", "home"}:
            missing = {"id", "source", "optional", "home"} - set(raw_document)
            raise AssemblyError(
                f"{field} is missing required fields: " + ", ".join(sorted(missing))
            )

        document_id = parse_document_id(raw_document["id"], f"{field}.id")
        source_value = raw_document["source"]
        optional = raw_document["optional"]
        home = raw_document["home"]
        if not isinstance(source_value, str):
            raise AssemblyError(f"{field}.source must be a string")
        if not isinstance(optional, bool):
            raise AssemblyError(f"{field}.optional must be boolean")
        if not isinstance(home, bool):
            raise AssemblyError(f"{field}.home must be boolean")
        source = safe_relative_path(source_value, f"{field}.source")
        if source.suffix.lower() != ".md":
            raise AssemblyError(f"{field}.source must be a Markdown file")
        if document_id in document_ids:
            raise AssemblyError(f"Duplicate publication document ID: {document_id}")
        if source in sources:
            raise AssemblyError(f"Duplicate publication source: {source.as_posix()}")
        document_ids.add(document_id)
        sources.add(source)
        documents.append(
            PublicationDocument(
                document_id=document_id,
                source=source,
                optional=optional,
                home=home,
                field=field,
            )
        )

    homes = [document for document in documents if document.home]
    if len(homes) != 1:
        raise AssemblyError("publication catalog must define exactly one home document")
    if homes[0].optional:
        raise AssemblyError("publication catalog home document must not be optional")
    return tuple(documents)


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
    has_page_field = any(key in raw_node for key in ("document", "destination"))

    if has_children:
        if has_page_field:
            raise AssemblyError(f"{field} must be either a section or a page, not both")
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

    unknown_keys = set(raw_node) - {"title", "document", "destination"}
    if unknown_keys:
        raise AssemblyError(
            f"{field} page contains unsupported fields: "
            + ", ".join(sorted(unknown_keys))
        )
    if set(raw_node) != {"title", "document", "destination"}:
        missing = {"title", "document", "destination"} - set(raw_node)
        raise AssemblyError(
            f"{field} page is missing required fields: " + ", ".join(sorted(missing))
        )

    document_id = parse_document_id(raw_node["document"], f"{field}.document")
    destination_value = raw_node["destination"]
    if not isinstance(destination_value, str):
        raise AssemblyError(f"{field}.destination must be a string")
    destination = safe_relative_path(destination_value, f"{field}.destination")
    if destination.suffix.lower() != ".md":
        raise AssemblyError(f"{field}.destination must be a Markdown file")
    return Page(
        title=title,
        document_id=document_id,
        destination=destination,
        field=field,
    )


def walk_nodes(nodes: tuple[NavigationNode, ...]):
    for node in nodes:
        yield node
        if isinstance(node, Section):
            yield from walk_nodes(node.children)


def page_nodes(nodes: tuple[NavigationNode, ...]) -> tuple[Page, ...]:
    return tuple(node for node in walk_nodes(nodes) if isinstance(node, Page))


def load_manifest(path: Path) -> tuple[NavigationNode, ...]:
    data = read_json_object(path, "site manifest")
    unknown_top_level = set(data) - {"navigation"}
    if unknown_top_level:
        raise AssemblyError(
            "site manifest contains unsupported top-level fields: "
            + ", ".join(sorted(unknown_top_level))
        )
    if not isinstance(data.get("navigation"), list):
        raise AssemblyError("site-manifest.json must contain a navigation array")
    if not data["navigation"]:
        raise AssemblyError("site-manifest.json navigation must not be empty")

    nodes = tuple(
        parse_navigation_node(node, f"navigation[{index}]")
        for index, node in enumerate(data["navigation"])
    )

    titles: set[str] = set()
    document_ids: set[str] = set()
    destinations: set[PurePosixPath] = set()
    for node in walk_nodes(nodes):
        if node.title in titles:
            raise AssemblyError(f"Duplicate navigation title: {node.title}")
        titles.add(node.title)
        if not isinstance(node, Page):
            continue
        if node.document_id in document_ids:
            raise AssemblyError(f"Duplicate publication document ID: {node.document_id}")
        if node.destination in destinations:
            raise AssemblyError(f"Duplicate destination: {node.destination.as_posix()}")
        document_ids.add(node.document_id)
        destinations.add(node.destination)

    return nodes


def validate_manifest_against_catalog(
    navigation: tuple[NavigationNode, ...],
    documents: tuple[PublicationDocument, ...],
) -> dict[str, PublicationDocument]:
    document_by_id = {document.document_id: document for document in documents}
    pages = page_nodes(navigation)
    page_ids = {page.document_id for page in pages}
    catalog_ids = set(document_by_id)

    unknown = sorted(page_ids - catalog_ids)
    if unknown:
        raise AssemblyError(
            "site manifest references unknown publication document IDs: "
            + ", ".join(unknown)
        )
    missing = sorted(catalog_ids - page_ids)
    if missing:
        raise AssemblyError(
            "site manifest does not cover publication document IDs: "
            + ", ".join(missing)
        )

    first_node = navigation[0]
    if not isinstance(first_node, Page):
        raise AssemblyError("The first navigation entry must be the home page")
    home = next(document for document in documents if document.home)
    if first_node.document_id != home.document_id:
        raise AssemblyError(
            f"The first navigation page must reference home document {home.document_id}"
        )
    if first_node.destination != PurePosixPath("index.md"):
        raise AssemblyError("The home page must generate index.md")
    return document_by_id


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


def source_file(
    source_root: Path,
    document: PublicationDocument,
) -> Path | None:
    current = source_root
    for part in document.source.parts:
        current /= part
        if current.is_symlink():
            raise AssemblyError(
                f"Publication source must not traverse a symlink: {document.source}"
            )
    if current.is_file():
        return current
    if document.optional:
        return None
    raise AssemblyError(f"Required publication source does not exist: {current}")


def include_navigation(
    nodes: tuple[NavigationNode, ...],
    document_by_id: dict[str, PublicationDocument],
    source_root: Path,
    docs_root: Path,
    skipped: list[str],
) -> tuple[NavigationNode, ...]:
    included: list[NavigationNode] = []
    for node in nodes:
        if isinstance(node, Section):
            children = include_navigation(
                node.children, document_by_id, source_root, docs_root, skipped
            )
            if children:
                included.append(
                    Section(title=node.title, children=children, field=node.field)
                )
            continue

        document = document_by_id[node.document_id]
        source_path = source_file(source_root, document)
        if source_path is None:
            skipped.append(document.document_id)
            continue
        destination_path = docs_root.joinpath(*node.destination.parts)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        included.append(node)
    return tuple(included)


def count_pages(nodes: tuple[NavigationNode, ...]) -> int:
    return len(page_nodes(nodes))


def assemble(source_root: Path, site_root: Path, output_root: Path) -> list[str]:
    source_root = source_root.resolve(strict=True)
    site_root = site_root.resolve(strict=True)
    output_root = output_root.resolve()

    documents = load_publication_catalog(
        source_root / "docs" / "publication-catalog.json"
    )
    navigation = load_manifest(site_root / "site-manifest.json")
    document_by_id = validate_manifest_against_catalog(navigation, documents)

    template_path = site_root / "zensical.template.toml"
    try:
        template = template_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
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
    included = include_navigation(
        navigation, document_by_id, source_root, docs_root, skipped
    )
    if not included or not isinstance(included[0], Page):
        raise AssemblyError("The included navigation must begin with the home page")

    copy_canonical_assets(source_root / "assets", docs_root / "assets")
    copy_directory_if_present(site_root / "assets", docs_root)

    config = template.replace(NAV_PLACEHOLDER, render_nav(included))
    (output_root / "zensical.toml").write_text(config, encoding="utf-8")

    summary = [
        f"assembled {count_pages(included)} page(s)",
        f"catalog documents: {len(documents)}",
        f"output: {output_root}",
    ]
    if skipped:
        summary.append("optional documents skipped: " + ", ".join(skipped))
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
