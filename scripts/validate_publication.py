#!/usr/bin/env python3
"""Validate Composition-specific publication semantics.

The generic schema-v3 publication protocol is owned by Site and is loaded from
an explicitly supplied reviewed checkout. This module retains only
Composition-owned publication classification, coverage, and glossary semantics.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_PATH = ROOT / "docs" / "publication-classification.json"
TRANSLATION_MANIFEST_PATH = ROOT / "translations" / "manifest.json"
SITE_PROTOCOL_ENV = "SITE_PUBLICATION_PROTOCOL_ROOT"
SITE_PROTOCOL_RELATIVE = Path("scripts/publication_contract.py")
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
IGNORED_ROOT_MARKDOWN_DISCOVERY_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".site-publication-protocol",
    ".venv",
    "__pycache__",
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


def _site_protocol_root(explicit_root: Path | None = None) -> Path:
    if explicit_root is not None:
        root = explicit_root
    else:
        configured = os.environ.get(SITE_PROTOCOL_ENV)
        if not configured:
            raise PublicationError(
                f"{SITE_PROTOCOL_ENV} must identify a reviewed Site protocol checkout"
            )
        root = Path(configured)
    if not root.is_absolute():
        root = ROOT / root
    try:
        return root.resolve(strict=True)
    except OSError as exc:
        raise PublicationError(f"Site publication protocol root is unavailable: {root}") from exc


def load_site_publication_protocol(explicit_root: Path | None = None) -> Any:
    protocol_root = _site_protocol_root(explicit_root)
    protocol_path = protocol_root / SITE_PROTOCOL_RELATIVE
    if not protocol_path.is_file() or protocol_path.is_symlink():
        raise PublicationError(
            "reviewed Site publication protocol file is unavailable: "
            f"{protocol_path}"
        )

    module_name = "_templates_site_publication_contract"
    spec = importlib.util.spec_from_file_location(module_name, protocol_path)
    if spec is None or spec.loader is None:
        raise PublicationError(f"unable to load Site publication protocol: {protocol_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise PublicationError(
            f"unable to execute Site publication protocol: {protocol_path}: {exc}"
        ) from exc

    for attribute in ("PublicationContractError", "load_publication_catalog"):
        if not hasattr(module, attribute):
            raise PublicationError(
                f"Site publication protocol is missing required interface: {attribute}"
            )
    return module


def load_publication_catalog(explicit_protocol_root: Path | None = None) -> Any:
    protocol = load_site_publication_protocol(explicit_protocol_root)
    try:
        return protocol.load_publication_catalog(
            ROOT,
            label="composition publication catalog",
        )
    except protocol.PublicationContractError as exc:
        raise PublicationError(f"Site publication protocol rejected catalog: {exc}") from exc


def strict_json(path: Path, label: str) -> dict[str, Any]:
    """Read a Composition-owned JSON contract with duplicate-member rejection."""
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


def safe_composition_path(value: Any, field: str) -> PurePosixPath:
    """Validate paths in Composition-owned maintenance metadata."""
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
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


def is_ignored_root_execution_path(relative: PurePosixPath) -> bool:
    return bool(relative.parts) and relative.parts[0] in IGNORED_ROOT_MARKDOWN_DISCOVERY_DIRS


def parse_publication_classification() -> dict[PurePosixPath, str]:
    data = strict_json(CLASSIFICATION_PATH, "publication classification")
    if set(data) != {"schema_version", "excluded_markdown"}:
        raise PublicationError(
            "publication classification must contain schema_version and excluded_markdown"
        )
    if data.get("schema_version") != 1 or type(data.get("schema_version")) is not int:
        raise PublicationError("publication classification schema_version must be integer 1")
    raw_exclusions = data.get("excluded_markdown")
    if not isinstance(raw_exclusions, list):
        raise PublicationError("publication classification excluded_markdown must be an array")

    exclusions: dict[PurePosixPath, str] = {}
    for index, raw in enumerate(raw_exclusions):
        field = f"excluded_markdown[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"source", "reason"}:
            raise PublicationError(f"{field} must contain source and reason")
        source = safe_composition_path(raw["source"], f"{field}.source")
        if source.suffix.lower() != ".md":
            raise PublicationError(f"{field}.source must be Markdown")
        if is_ignored_root_execution_path(source):
            raise PublicationError(f"{field}.source must be repository source Markdown")
        reason = raw["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise PublicationError(f"{field}.reason must be non-empty")
        if source in exclusions:
            raise PublicationError(f"duplicate excluded Markdown source: {source}")
        resolve_regular(source, f"{field}.source")
        exclusions[source] = reason.strip()
    return exclusions


def parse_translation_classification() -> set[PurePosixPath]:
    """Return derivative Markdown paths declared by the translation manifest.

    Full translation semantics are validated by ``validate_translations.py``.
    Publication classification only needs a safe, existing, unique derivative
    path set so translations form a third disjoint Markdown class instead of
    being duplicated in ``publication-classification.json``.
    """
    data = strict_json(TRANSLATION_MANIFEST_PATH, "translation manifest")
    if set(data) != {"schema_version", "canonical_language", "translations"}:
        raise PublicationError(
            "translation manifest must contain schema_version, canonical_language, "
            "and translations"
        )
    if data.get("schema_version") != 2 or type(data.get("schema_version")) is not int:
        raise PublicationError("translation manifest schema_version must be integer 2")
    if data.get("canonical_language") != "en":
        raise PublicationError("translation manifest canonical_language must be en")
    raw_translations = data.get("translations")
    if not isinstance(raw_translations, list):
        raise PublicationError("translation manifest translations must be an array")

    translations: set[PurePosixPath] = set()
    for index, raw in enumerate(raw_translations):
        field = f"translations[{index}]"
        if not isinstance(raw, dict) or "translation" not in raw:
            raise PublicationError(f"{field} must declare a translation path")
        translation = safe_composition_path(raw["translation"], f"{field}.translation")
        if translation.suffix.lower() != ".md":
            raise PublicationError(f"{field}.translation must be Markdown")
        if not translation.parts or translation.parts[0] != "translations":
            raise PublicationError(
                f"{field}.translation must be beneath the translations directory"
            )
        if translation in translations:
            raise PublicationError(f"duplicate translation Markdown source: {translation}")
        resolve_regular(translation, f"{field}.translation")
        translations.add(translation)
    return translations


def discover_repository_markdown() -> set[PurePosixPath]:
    discovered: set[PurePosixPath] = set()
    pending = [ROOT]
    while pending:
        directory = pending.pop()
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = PurePosixPath(child.relative_to(ROOT).as_posix())
            if child.is_dir() and is_ignored_root_execution_path(relative):
                continue
            if child.is_symlink():
                raise PublicationError(
                    f"repository Markdown discovery must not traverse symlink: {relative}"
                )
            if child.is_dir():
                pending.append(child)
                continue
            if child.is_file() and child.suffix.lower() == ".md":
                discovered.add(relative)
    return discovered


def validate_composition_catalog_declarations(catalog: Any) -> None:
    homes = [document for document in catalog.documents if document.home]
    if len(homes) != 1 or homes[0].source != PurePosixPath("README.md"):
        raise PublicationError("Composition publication home must be README.md")
    if catalog.glossary_source != PurePosixPath("docs/glossary.yml"):
        raise PublicationError("Composition glossary declaration must be docs/glossary.yml")


def validate_markdown_partition(
    published: set[PurePosixPath],
    excluded: set[PurePosixPath],
    translated: set[PurePosixPath],
    discovered: set[PurePosixPath],
) -> None:
    published_excluded = sorted(path.as_posix() for path in published & excluded)
    if published_excluded:
        raise PublicationError(
            "Markdown must not be both published and explicitly excluded: "
            + ", ".join(published_excluded)
        )
    published_translated = sorted(path.as_posix() for path in published & translated)
    if published_translated:
        raise PublicationError(
            "Markdown must not be both published and translation-declared: "
            + ", ".join(published_translated)
        )
    excluded_translated = sorted(path.as_posix() for path in excluded & translated)
    if excluded_translated:
        raise PublicationError(
            "Markdown must not be both explicitly excluded and translation-declared: "
            + ", ".join(excluded_translated)
        )

    classified = published | excluded | translated
    missing = sorted(path.as_posix() for path in discovered - classified)
    if missing:
        raise PublicationError(
            "repository Markdown lacks explicit publication classification: "
            + ", ".join(missing)
        )
    unknown = sorted(path.as_posix() for path in classified - discovered)
    if unknown:
        raise PublicationError(
            "Markdown publication classification references undiscovered source: "
            + ", ".join(unknown)
        )


def validate_markdown_classification(
    catalog: Any,
    exclusions: dict[PurePosixPath, str],
    translations: set[PurePosixPath],
) -> None:
    published = {document.source for document in catalog.documents}
    validate_markdown_partition(
        published,
        set(exclusions),
        translations,
        discover_repository_markdown(),
    )


def asset_covers(catalog: Any, relative: PurePosixPath) -> bool:
    for asset in catalog.assets:
        if asset.source == relative or asset.source in relative.parents:
            return True
    return False


def reader_material(source: str) -> bool:
    path = PurePosixPath(source)
    return path.suffix.lower() == ".md" and (
        str(path).startswith("files/docs/") or path.name in READER_BASENAMES
    )


def validate_reader_coverage(catalog: Any) -> None:
    document_sources = {document.source for document in catalog.documents}
    required = {
        PurePosixPath("README.md"),
        PurePosixPath("docs/index.md"),
        PurePosixPath("docs/publication-catalog.md"),
        PurePosixPath("docs/migrations/composition-authority-migration.md"),
        PurePosixPath("catalog/README.md"),
        PurePosixPath("schemas/README.md"),
    }
    required.update(
        PurePosixPath(path.relative_to(ROOT).as_posix())
        for path in (ROOT / "docs" / "architecture").glob("*.md")
    )

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
        raise PublicationError(
            "reader-facing Markdown is missing from publication catalog: "
            + ", ".join(missing)
        )


def validate_machine_coverage(catalog: Any) -> None:
    required_assets = {
        PurePosixPath("catalog/catalog.json"),
        PurePosixPath("recipes"),
        PurePosixPath("release/composition-installer.json"),
    }
    required_assets.update(
        PurePosixPath(path.relative_to(ROOT).as_posix())
        for path in (ROOT / "schemas").glob("*.json")
    )
    required_assets.update(
        PurePosixPath(f"components/{component_id}/component.json")
        for component_id in strict_json(
            ROOT / "catalog" / "catalog.json",
            "production catalog",
        ).get("components", [])
    )
    missing = sorted(
        path.as_posix() for path in required_assets if not asset_covers(catalog, path)
    )
    if missing:
        raise PublicationError(
            "machine-readable authority is missing from publication assets: "
            + ", ".join(missing)
        )


def validate_glossary(catalog: Any) -> None:
    if catalog.glossary_source is None:
        raise PublicationError("Composition publication must declare a glossary")
    path = resolve_regular(catalog.glossary_source, "glossary.source")
    data = strict_json(path, "Composition glossary")
    if set(data) != {"schema_version", "terms"} or data.get("schema_version") != 1:
        raise PublicationError("Composition glossary must use schema version 1")
    terms = data.get("terms")
    if not isinstance(terms, list) or not terms:
        raise PublicationError("Composition glossary terms must be a non-empty array")
    ids: set[str] = set()
    for index, term in enumerate(terms):
        if not isinstance(term, dict):
            raise PublicationError(f"glossary term {index} must be an object")
        term_id = term.get("id")
        if not isinstance(term_id, str) or not TERM_RE.fullmatch(term_id):
            raise PublicationError(f"glossary term {index} has invalid id")
        if term_id in ids:
            raise PublicationError(f"duplicate glossary term id: {term_id}")
        ids.add(term_id)
    obsolete = sorted(ids & OBSOLETE_TERM_IDS)
    if obsolete:
        raise PublicationError(
            "Composition glossary contains retired copy-model terms: "
            + ", ".join(obsolete)
        )


def main() -> int:
    try:
        catalog = load_publication_catalog()
        exclusions = parse_publication_classification()
        translations = parse_translation_classification()
        validate_composition_catalog_declarations(catalog)
        validate_reader_coverage(catalog)
        validate_markdown_classification(catalog, exclusions, translations)
        validate_machine_coverage(catalog)
        validate_glossary(catalog)
    except PublicationError as exc:
        print(f"composition publication validation failed: {exc}", file=sys.stderr)
        return 1
    print("Composition publication validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
