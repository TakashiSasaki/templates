#!/usr/bin/env python3
"""Validate the composition provider publication boundary with stdlib only."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs" / "publication-catalog.json"
GLOSSARY_PATH = ROOT / "docs" / "glossary.yml"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TERM_RE = re.compile(r"^(?:templates|external)-[a-z0-9]+(?:-[a-z0-9]+)*$")
READER_BASENAMES = {
    "README.md",
    "SKILL.md",
    "TEMPLATE.md",
    "RUNTIME.md",
    "CLI_INTERFACE.md",
    "MCP_INTERFACE.md",
    "MCP_APPS.md",
    "WEB_INTERFACE.md",
    "SERVICE_INTERFACE.md",
}
OBSOLETE_TERM_IDS = {
    "templates-skill-mcp-extension",
    "templates-skill-runtime-decision-record",
    "templates-skill-public-interface-selection-contract",
    "templates-webapp-template-source-artifact",
    "templates-webapp-template-distribution-artifact",
}


class PublicationError(RuntimeError):
    pass


def strict_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PublicationError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PublicationError(f"{label} contains duplicate member: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise PublicationError(f"{label} contains non-standard numeric constant: {value}")

    try:
        value = json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise PublicationError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"{label} must be a JSON object")
    return value


def safe_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise PublicationError(f"{field} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part.casefold() == ".git" for part in parts):
        raise PublicationError(f"{field} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise PublicationError(f"{field} must be a safe relative POSIX path")
    return path


def resolve_regular(relative: PurePosixPath, field: str) -> Path:
    current = ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise PublicationError(f"{field} must not traverse a symlink: {relative}")
    if not current.is_file():
        raise PublicationError(f"{field} must name an existing regular file: {relative}")
    return current


def paths_overlap(first: PurePosixPath, second: PurePosixPath) -> bool:
    return first == second or first in second.parents or second in first.parents


def walk_asset(relative: PurePosixPath, field: str) -> list[Path]:
    current = ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise PublicationError(f"{field} must not traverse a symlink: {relative}")
    if current.is_file():
        if current.suffix.lower() == ".md":
            raise PublicationError(f"{field} must not publish Markdown as an asset: {relative}")
        return [current]
    if not current.is_dir():
        raise PublicationError(f"{field} must exist: {relative}")
    files: list[Path] = []
    pending = [current]
    while pending:
        directory = pending.pop()
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            if child.is_symlink():
                raise PublicationError(f"{field} contains a symlink: {child.relative_to(ROOT)}")
            if child.is_dir():
                pending.append(child)
                continue
            if not child.is_file():
                raise PublicationError(f"{field} contains unsupported entry: {child.relative_to(ROOT)}")
            if child.suffix.lower() == ".md":
                raise PublicationError(f"{field} contains undeclared Markdown: {child.relative_to(ROOT)}")
            files.append(child)
    if not files:
        raise PublicationError(f"{field} must not be empty: {relative}")
    return files


def parse_catalog() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], PurePosixPath]:
    data = strict_json(CATALOG_PATH, "publication catalog")
    if set(data) != {"schema_version", "documents", "assets", "glossary"}:
        raise PublicationError("publication catalog must contain schema_version, documents, assets, and glossary")
    if data.get("schema_version") != 3 or type(data.get("schema_version")) is not int:
        raise PublicationError("publication catalog schema_version must be integer 3")

    documents: dict[str, dict[str, Any]] = {}
    sources: set[PurePosixPath] = set()
    homes = 0
    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise PublicationError("publication catalog documents must be non-empty")
    for index, raw in enumerate(raw_documents):
        field = f"documents[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"id", "source", "optional", "home"}:
            raise PublicationError(f"{field} has invalid fields")
        doc_id = raw["id"]
        if not isinstance(doc_id, str) or not NAME_RE.fullmatch(doc_id):
            raise PublicationError(f"{field}.id must be lowercase kebab-case")
        source = safe_path(raw["source"], f"{field}.source")
        if source.suffix.lower() != ".md":
            raise PublicationError(f"{field}.source must be Markdown")
        if type(raw["optional"]) is not bool or type(raw["home"]) is not bool:
            raise PublicationError(f"{field}.optional and home must be boolean")
        if doc_id in documents or source in sources:
            raise PublicationError("publication document IDs and sources must be unique")
        resolve_regular(source, f"{field}.source")
        if raw["home"]:
            homes += 1
            if raw["optional"]:
                raise PublicationError("publication home must not be optional")
        documents[doc_id] = {"source": source, "optional": raw["optional"], "home": raw["home"]}
        sources.add(source)
    if homes != 1:
        raise PublicationError("publication catalog must define exactly one home")

    raw_assets = data.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise PublicationError("publication catalog assets must be non-empty")
    assets: list[dict[str, Any]] = []
    source_paths: list[PurePosixPath] = []
    destination_paths: list[PurePosixPath] = []
    for index, raw in enumerate(raw_assets):
        field = f"assets[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"source", "destination", "optional"}:
            raise PublicationError(f"{field} has invalid fields")
        source = safe_path(raw["source"], f"{field}.source")
        destination = safe_path(raw["destination"], f"{field}.destination")
        if type(raw["optional"]) is not bool:
            raise PublicationError(f"{field}.optional must be boolean")
        walk_asset(source, f"{field}.source")
        assets.append({"source": source, "destination": destination, "optional": raw["optional"]})
        source_paths.append(source)
        destination_paths.append(destination)
    for label, values in (("asset sources", source_paths), ("asset destinations", destination_paths)):
        if len(values) != len(set(values)):
            raise PublicationError(f"{label} must be unique")
        for index, first in enumerate(values):
            for second in values[index + 1:]:
                if paths_overlap(first, second):
                    raise PublicationError(f"{label} must not overlap: {first} and {second}")

    glossary = data.get("glossary")
    if not isinstance(glossary, dict) or set(glossary) != {"source"}:
        raise PublicationError("publication catalog glossary must contain only source")
    glossary_source = safe_path(glossary["source"], "glossary.source")
    resolve_regular(glossary_source, "glossary.source")
    return documents, assets, glossary_source


def asset_covers(assets: list[dict[str, Any]], relative: PurePosixPath) -> bool:
    for asset in assets:
        source = asset["source"]
        if source == relative or source in relative.parents:
            return True
    return False


def reader_material(source: str) -> bool:
    path = PurePosixPath(source)
    return path.suffix.lower() == ".md" and (
        str(path).startswith("files/docs/") or path.name in READER_BASENAMES
    )


def validate_reader_coverage(documents: dict[str, dict[str, Any]]) -> None:
    document_sources = {entry["source"] for entry in documents.values()}
    required = {
        PurePosixPath("README.md"),
        PurePosixPath("docs/index.md"),
        PurePosixPath("docs/publication-catalog.md"),
        PurePosixPath("catalog/README.md"),
        PurePosixPath("schemas/README.md"),
    }
    required.update(PurePosixPath(path.relative_to(ROOT).as_posix()) for path in (ROOT / "docs" / "architecture").glob("*.md"))
    required.update(PurePosixPath(path.relative_to(ROOT).as_posix()) for path in (ROOT / "docs" / "migrations").glob("*.md"))

    production = strict_json(ROOT / "catalog" / "catalog.json", "production catalog")
    for component_id in production.get("components", []):
        descriptor_path = ROOT / "components" / component_id / "component.json"
        descriptor = strict_json(descriptor_path, f"descriptor {component_id}")
        for material in descriptor.get("materials", []):
            source = material.get("source") if isinstance(material, dict) else None
            if isinstance(source, str) and reader_material(source):
                required.add(PurePosixPath(f"components/{component_id}/{source}"))
    missing = sorted(path.as_posix() for path in required - document_sources)
    if missing:
        raise PublicationError("reader-facing Markdown is missing from publication catalog: " + ", ".join(missing))


def validate_machine_coverage(assets: list[dict[str, Any]]) -> None:
    required = {PurePosixPath("catalog/catalog.json"), PurePosixPath("recipes")}
    required.update(PurePosixPath(path.relative_to(ROOT).as_posix()) for path in (ROOT / "schemas").glob("*.json"))
    production = strict_json(ROOT / "catalog" / "catalog.json", "production catalog")
    for component_id in production.get("components", []):
        required.add(PurePosixPath(f"components/{component_id}/component.json"))
    missing = sorted(path.as_posix() for path in required if not asset_covers(assets, path))
    if missing:
        raise PublicationError("machine-readable production authority is missing from publication assets: " + ", ".join(missing))


def validate_glossary(glossary_source: PurePosixPath) -> None:
    glossary = strict_json(ROOT / glossary_source, "composition glossary")
    if set(glossary) != {"schema_version", "terms"} or glossary.get("schema_version") != 1:
        raise PublicationError("composition glossary must have schema_version 1 and terms")
    terms = glossary.get("terms")
    if not isinstance(terms, list) or not terms:
        raise PublicationError("composition glossary terms must be non-empty")
    ids: set[str] = set()
    for index, term in enumerate(terms):
        field = f"terms[{index}]"
        if not isinstance(term, dict):
            raise PublicationError(f"{field} must be an object")
        term_id = term.get("id")
        if not isinstance(term_id, str) or not TERM_RE.fullmatch(term_id):
            raise PublicationError(f"{field}.id is invalid")
        if term_id in ids:
            raise PublicationError(f"duplicate glossary term id: {term_id}")
        ids.add(term_id)
        if not isinstance(term.get("term"), str) or not term["term"].strip():
            raise PublicationError(f"{field}.term must be non-empty")
        origin = term.get("origin")
        if origin == "repository":
            if not isinstance(term.get("definition"), str) or not term["definition"].strip():
                raise PublicationError(f"{field} repository term requires definition")
        elif origin == "external":
            if not isinstance(term.get("summary"), str) or not term["summary"].strip():
                raise PublicationError(f"{field} external term requires summary")
            authority = term.get("authority")
            if not isinstance(authority, dict) or not authority.get("sources"):
                raise PublicationError(f"{field} external term requires authority sources")
        else:
            raise PublicationError(f"{field}.origin must be repository or external")
        related = term.get("related_terms", [])
        if not isinstance(related, list) or any(not isinstance(value, str) or not TERM_RE.fullmatch(value) for value in related):
            raise PublicationError(f"{field}.related_terms is invalid")
    obsolete = sorted(ids & OBSOLETE_TERM_IDS)
    if obsolete:
        raise PublicationError("obsolete copyable-template glossary IDs must not return: " + ", ".join(obsolete))
    required_ids = {
        "templates-skill-profile",
        "templates-composition-component",
        "templates-composition-recipe",
        "templates-composition-lock",
        "templates-contract-manifest",
        "templates-implementation-evidence",
        "templates-release-evidence",
        "templates-release-bundle",
        "external-mcp-model-context-protocol",
    }
    missing = sorted(required_ids - ids)
    if missing:
        raise PublicationError("required composition glossary terms are missing: " + ", ".join(missing))


def validate_publication_root() -> None:
    documents, assets, glossary_source = parse_catalog()
    validate_reader_coverage(documents)
    validate_machine_coverage(assets)
    validate_glossary(glossary_source)


def main() -> int:
    try:
        validate_publication_root()
    except PublicationError as exc:
        print(f"composition publication validation failed: {exc}", file=sys.stderr)
        return 1
    print("Composition publication validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
