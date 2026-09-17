"""Publication identities, closure inputs and safe materialization primitives."""
from __future__ import annotations
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from integration.materialize_publication_assets import (
    PublicationMaterializationError,
    load_materialized_publication_catalog,
)
from integration.publication_contract import (
    PublicationContractError,
    parse_name as contract_parse_name,
    resolve_without_symlinks,
    safe_relative_path,
)

AUDIENCE_TITLES: dict[str, str] = {
    "use": "Use templates",
    "maintain": "Maintain templates",
}

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

