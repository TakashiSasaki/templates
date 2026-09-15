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
    try:
        return safe_relative_path(value, field)
    except PublicationContractError as exc:
        raise AssemblyError(str(exc)) from exc


def parse_name(value: Any, field: str) -> str:
    try:
        return contract_parse_name(value, field)
    except PublicationContractError as exc:
        raise AssemblyError(str(exc)) from exc


def resolve(root: Path, relative: PurePosixPath, field: str) -> Path:
    try:
        return resolve_without_symlinks(root, relative, field)
    except PublicationContractError as exc:
        raise AssemblyError(str(exc)) from exc


def load_catalog(
    name: str,
    root: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    try:
        catalog = load_materialized_publication_catalog(root, name)
    except PublicationMaterializationError as exc:
        raise AssemblyError(str(exc)) from exc

    documents = {
        document.document_id: {
            "source": document.source,
            "optional": document.optional,
            "home": document.home,
        }
        for document in catalog.documents
    }
    assets = [
        {
            "source": asset.source,
            "destination": asset.destination,
            "optional": asset.optional,
        }
        for asset in catalog.assets
    ]
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


AUDIENCE_TITLES: dict[str, str] = {
    "use": "Use templates",
    "maintain": "Maintain templates",
}


class Manifest(tuple):
    home: tuple[str, str]
    projected_navigation: list[dict[str, Any]]
    schema_version: int
    audiences: list[str]
    documents: list[dict[str, Any]]
    navigation: dict[str, list[dict[str, Any]]] | list[dict[str, Any]]
    document_by_key: dict[tuple[str, str], dict[str, Any]]
    document_by_destination: dict[PurePosixPath, dict[str, Any]]

    def __new__(
        cls,
        home: tuple[str, str],
        projected_navigation: list[dict[str, Any]],
        *,
        schema_version: int,
        audiences: list[str],
        documents: list[dict[str, Any]],
        navigation: dict[str, list[dict[str, Any]]] | list[dict[str, Any]],
        document_by_key: dict[tuple[str, str], dict[str, Any]],
        document_by_destination: dict[PurePosixPath, dict[str, Any]],
    ) -> Manifest:
        instance = super().__new__(cls, (home, projected_navigation))
        instance.home = home
        instance.projected_navigation = projected_navigation
        instance.schema_version = schema_version
        instance.audiences = audiences
        instance.documents = documents
        instance.navigation = navigation
        instance.document_by_key = document_by_key
        instance.document_by_destination = document_by_destination
        return instance


def pages(
    nodes: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
) -> Iterator[dict[str, Any]]:
    if isinstance(nodes, dict):
        for tree in nodes.values():
            yield from pages(tree)
        return
    for node in nodes:
        if "children" in node:
            yield from pages(node["children"])
        else:
            yield node


def parse_manifest(data: dict[str, Any]) -> Manifest:
    schema_version = data.get("schema_version")
    if type(schema_version) is not int:
        raise AssemblyError("site manifest schema_version must be an integer")
    if schema_version == 2:
        if set(data) != {"schema_version", "home", "navigation"}:
            raise AssemblyError(
                "site manifest schema version 2 must contain only schema_version, home, and navigation"
            )
        home_data = data["home"]
        if not isinstance(home_data, dict) or set(home_data) != {"publication", "document"}:
            raise AssemblyError(
                "site manifest home must identify publication and document"
            )
        home = (
            parse_name(home_data["publication"], "home.publication"),
            parse_name(home_data["document"], "home.document"),
        )
        navigation_data = data["navigation"]
        if not isinstance(navigation_data, list) or not navigation_data:
            raise AssemblyError("site manifest navigation must be non-empty")
        parsed_navigation = [
            parse_node(value, f"navigation[{index}]")
            for index, value in enumerate(navigation_data)
        ]
        parsed_pages = list(pages(parsed_navigation))
        doc_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        doc_by_dest: dict[PurePosixPath, dict[str, Any]] = {}
        canonical_docs: list[dict[str, Any]] = []
        for page in parsed_pages:
            key = (page["publication"], page["document"])
            dest = page["destination"]
            if key in doc_by_key or dest in doc_by_dest:
                raise AssemblyError(
                    "site manifest document keys and destinations must be unique"
                )
            doc_entry = {
                "publication": page["publication"],
                "document": page["document"],
                "title": page["title"],
                "destination": dest,
                "primary_audience": "use",
                "additional_audiences": [],
            }
            doc_by_key[key] = doc_entry
            doc_by_dest[dest] = doc_entry
            canonical_docs.append(doc_entry)

        return Manifest(
            home,
            parsed_navigation,
            schema_version=2,
            audiences=[],
            documents=canonical_docs,
            navigation=parsed_navigation,
            document_by_key=doc_by_key,
            document_by_destination=doc_by_dest,
        )

    if schema_version == 3:
        if set(data) != {"schema_version", "audiences", "home", "documents", "navigation"}:
            raise AssemblyError(
                "site manifest schema version 3 must contain exactly schema_version, audiences, home, documents, and navigation"
            )
        audiences_data = data["audiences"]
        if (
            not isinstance(audiences_data, list)
            or audiences_data != ["use", "maintain"]
        ):
            raise AssemblyError(
                "site manifest audiences must be exactly ['use', 'maintain']"
            )
        audiences = list(audiences_data)

        home_data = data["home"]
        if not isinstance(home_data, dict) or set(home_data) != {"publication", "document"}:
            raise AssemblyError(
                "site manifest home must identify publication and document"
            )
        home = (
            parse_name(home_data["publication"], "home.publication"),
            parse_name(home_data["document"], "home.document"),
        )

        documents_data = data["documents"]
        if not isinstance(documents_data, list) or not documents_data:
            raise AssemblyError("site manifest documents must be a non-empty array")

        doc_by_key = {}
        doc_by_dest = {}
        canonical_docs = []
        expected_doc_keys = {"publication", "document", "title", "destination", "primary_audience", "additional_audiences"}
        for index, item in enumerate(documents_data):
            field = f"documents[{index}]"
            if not isinstance(item, dict) or set(item) != expected_doc_keys:
                raise AssemblyError(
                    f"{field} must contain exactly publication, document, title, destination, primary_audience, and additional_audiences"
                )
            pub = parse_name(item["publication"], f"{field}.publication")
            doc = parse_name(item["document"], f"{field}.document")
            dest = safe_path(item["destination"], f"{field}.destination")
            if dest.suffix.lower() != ".md":
                raise AssemblyError(f"{field}.destination must be a Markdown path (.md)")
            title = item["title"]
            if not isinstance(title, str) or not title.strip():
                raise AssemblyError(f"{field}.title must be a non-empty string")
            title = title.strip()
            primary_aud = item["primary_audience"]
            if not isinstance(primary_aud, str) or primary_aud not in audiences:
                raise AssemblyError(f"{field}.primary_audience must be one of {audiences}")
            additional_aud = item["additional_audiences"]
            if (
                not isinstance(additional_aud, list)
                or any(not isinstance(a, str) or a not in audiences or a == primary_aud for a in additional_aud)
                or len(set(additional_aud)) != len(additional_aud)
            ):
                raise AssemblyError(
                    f"{field}.additional_audiences must be a list of unique audiences excluding primary_audience"
                )
            key = (pub, doc)
            if key in doc_by_key:
                raise AssemblyError(f"duplicate document key in site manifest documents: {pub}:{doc}")
            if dest in doc_by_dest:
                raise AssemblyError(f"duplicate document destination in site manifest documents: {dest}")
            doc_entry = {
                "publication": pub,
                "document": doc,
                "title": title,
                "destination": dest,
                "primary_audience": primary_aud,
                "additional_audiences": list(additional_aud),
            }
            doc_by_key[key] = doc_entry
            doc_by_dest[dest] = doc_entry
            canonical_docs.append(doc_entry)

        if home not in doc_by_key:
            raise AssemblyError(f"site manifest home document {home[0]}:{home[1]} is not in documents")
        if doc_by_key[home]["destination"] != PurePosixPath("index.md"):
            raise AssemblyError("site manifest home document must have destination index.md")

        navigation_data = data["navigation"]
        if not isinstance(navigation_data, dict) or set(navigation_data) != set(audiences):
            raise AssemblyError(f"site manifest navigation must be an object with keys matching audiences {audiences}")

        parsed_navigation: dict[str, list[dict[str, Any]]] = {}
        for audience in audiences:
            aud_nav = navigation_data[audience]
            if not isinstance(aud_nav, list) or not aud_nav:
                raise AssemblyError(f"site manifest navigation[{audience!r}] must be a non-empty array")
            parsed_aud_nav = [
                parse_node(value, f"navigation.{audience}[{idx}]")
                for idx, value in enumerate(aud_nav)
            ]
            aud_pages = list(pages(parsed_aud_nav))
            aud_seen_keys: set[tuple[str, str]] = set()
            for page in aud_pages:
                page_key = (page["publication"], page["document"])
                aud_seen_keys.add(page_key)
                if page_key not in doc_by_key:
                    raise AssemblyError(
                        f"navigation for audience {audience!r} references undeclared document: {page_key[0]}:{page_key[1]}"
                    )
                target_doc = doc_by_key[page_key]
                if page["destination"] != target_doc["destination"]:
                    raise AssemblyError(
                        f"navigation page destination mismatch for {page_key[0]}:{page_key[1]}: "
                        f"expected {target_doc['destination']}, got {page['destination']}"
                    )
                doc_audiences = {target_doc["primary_audience"], *target_doc["additional_audiences"]}
                if audience not in doc_audiences:
                    raise AssemblyError(
                        f"document {page_key[0]}:{page_key[1]} is in navigation for {audience!r} "
                        f"but does not declare that audience"
                    )

            for doc_entry in canonical_docs:
                doc_audiences = {doc_entry["primary_audience"], *doc_entry["additional_audiences"]}
                if audience in doc_audiences:
                    d_key = (doc_entry["publication"], doc_entry["document"])
                    if d_key not in aud_seen_keys:
                        raise AssemblyError(
                            f"document {d_key[0]}:{d_key[1]} declares audience {audience!r} "
                            f"but is missing from navigation.{audience}"
                        )
            parsed_navigation[audience] = parsed_aud_nav

        projected_navigation = [
            {
                "title": AUDIENCE_TITLES.get(audience, audience),
                "children": parsed_navigation[audience],
            }
            for audience in audiences
        ]

        return Manifest(
            home,
            projected_navigation,
            schema_version=3,
            audiences=audiences,
            documents=canonical_docs,
            navigation=parsed_navigation,
            document_by_key=doc_by_key,
            document_by_destination=doc_by_dest,
        )

    raise AssemblyError("site manifest must be schema version 2 or 3")


def load_manifest(path: Path) -> Manifest:
    return parse_manifest(read_json(path, "site manifest"))


def asset_entries(source: Path, field: str) -> list[Path]:
    """Return an asset tree without ever following directory symlinks."""
    if source.is_symlink():
        raise AssemblyError(f"{field} must not be a symlink")
    if source.is_file():
        return [source]
    if not source.is_dir():
        return []

    result: list[Path] = []
    pending = [source]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise AssemblyError(f"unable to inspect {field} {directory}: {exc}") from exc
        for item in children:
            relative_item = item.relative_to(source)
            if any(part.casefold() == ".git" for part in relative_item.parts):
                raise AssemblyError(f"{field} contains a .git subtree: {item}")
            if item.is_symlink():
                raise AssemblyError(f"{field} contains a symlink: {item}")
            result.append(item)
            if item.is_dir():
                pending.append(item)
    return result


def copy_asset(
    source: Path,
    destination: Path,
    field: str,
    *,
    skip_markdown: bool = False,
) -> None:
    entries = asset_entries(source, field)
    if not entries:
        raise AssemblyError(f"{field} does not exist or is empty: {source}")

    for item in entries:
        if not item.is_file():
            continue
        relative_item = Path() if source.is_file() else item.relative_to(source)
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
