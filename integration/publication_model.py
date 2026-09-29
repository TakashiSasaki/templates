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
from integration.publication_contract_v4 import load_publication_catalog_v4

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
    catalog_path = root / "docs/publication-catalog.json"
    try:
        raw_version = json.loads(catalog_path.read_text(encoding="utf-8"))["schema_version"]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise AssemblyError(f"unable to inspect {name} publication catalog: {exc}") from exc
    if raw_version == 4:
        try:
            catalog = load_publication_catalog_v4(root, label=f"{name} catalog")
        except Exception as exc:
            raise AssemblyError(str(exc)) from exc
    else:
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
            "source_kind": getattr(asset, "source_kind", "tracked"),
        }
        for asset in catalog.assets
    ]
    return documents, assets


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
