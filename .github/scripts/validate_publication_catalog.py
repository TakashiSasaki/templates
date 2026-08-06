#!/usr/bin/env python3
"""Validate the Skill documentation publication catalog."""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_KEYS = {"documents", "schema_version"}
DOCUMENT_KEYS = {"home", "id", "optional", "source"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ValidationError(Exception):
    """Raised when the publication catalog violates its contract."""


@dataclass(frozen=True)
class Document:
    id: str
    source: str
    optional: bool
    home: bool


def _validate_exact_keys(value: Any, expected: set[str], field: str) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be an object")

    actual = set(value)
    if actual == expected:
        return

    details: list[str] = []
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        details.append(f"missing: {', '.join(missing)}")
    if unknown:
        details.append(f"unsupported: {', '.join(unknown)}")
    raise ValidationError(f"{field} fields are invalid ({'; '.join(details)})")


def _read_catalog(path: Path) -> Any:
    if path.is_symlink():
        raise ValidationError(f"Publication catalog must not be a symlink: {path}")

    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise ValidationError(f"Publication catalog does not exist: {path}") from exc
    except PermissionError as exc:
        raise ValidationError(f"Unable to read publication catalog {path}: {exc}") from exc

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"Invalid publication catalog JSON {path}: content is not valid UTF-8"
        ) from exc

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid publication catalog JSON {path}: {exc}") from exc


def _validate_source(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{field} must be a non-empty string")

    parts = value.split("/")
    unsafe = (
        value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in parts)
    )
    if unsafe:
        raise ValidationError(f"{field} must be a safe relative POSIX path: {value!r}")

    if not value.lower().endswith(".md"):
        raise ValidationError(f"{field} must identify a Markdown file")

    return value


def _validate_source_file(root: Path, source: str, field: str) -> None:
    candidate = root
    for part in source.split("/"):
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValidationError(f"{field} traverses a symlink: {source}")

    try:
        mode = candidate.stat().st_mode
    except FileNotFoundError as exc:
        raise ValidationError(
            f"{field} does not identify an existing regular file: {source}"
        ) from exc

    if not stat.S_ISREG(mode):
        raise ValidationError(
            f"{field} does not identify an existing regular file: {source}"
        )


def _parse_document(raw_document: Any, index: int, root: Path) -> Document:
    field = f"documents[{index}]"
    _validate_exact_keys(raw_document, DOCUMENT_KEYS, field)

    document_id = raw_document["id"]
    if not isinstance(document_id, str) or ID_PATTERN.fullmatch(document_id) is None:
        raise ValidationError(f"{field}.id must use lowercase kebab-case")

    source = _validate_source(raw_document["source"], f"{field}.source")
    optional = raw_document["optional"]
    home = raw_document["home"]
    if type(optional) is not bool:
        raise ValidationError(f"{field}.optional must be boolean")
    if type(home) is not bool:
        raise ValidationError(f"{field}.home must be boolean")

    _validate_source_file(root, source, field)
    return Document(id=document_id, source=source, optional=optional, home=home)


def _duplicate_value(values: list[str]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


def validate(
    catalog_path: str | os.PathLike[str],
    root: str | os.PathLike[str] = ".",
) -> list[Document]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise ValidationError(f"Repository root does not exist: {root_path}")

    resolved_catalog_path = Path(catalog_path).expanduser()
    if not resolved_catalog_path.is_absolute():
        resolved_catalog_path = root_path / resolved_catalog_path

    catalog = _read_catalog(resolved_catalog_path)
    _validate_exact_keys(catalog, ROOT_KEYS, "publication catalog")

    schema_version = catalog["schema_version"]
    if type(schema_version) is not int or schema_version != 1:
        raise ValidationError(
            "publication catalog schema_version must be 1 and use an integer JSON value"
        )

    raw_documents = catalog["documents"]
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ValidationError("publication catalog documents must be a non-empty array")

    documents = [
        _parse_document(raw_document, index, root_path)
        for index, raw_document in enumerate(raw_documents)
    ]

    duplicate_id = _duplicate_value([document.id for document in documents])
    if duplicate_id is not None:
        raise ValidationError(f"Duplicate publication document id: {duplicate_id}")

    duplicate_source = _duplicate_value([document.source for document in documents])
    if duplicate_source is not None:
        raise ValidationError(f"Duplicate publication document source: {duplicate_source}")

    home_documents = [document for document in documents if document.home]
    if len(home_documents) != 1:
        raise ValidationError("publication catalog must select exactly one home document")
    if home_documents[0].optional:
        raise ValidationError("publication catalog home document must not be optional")

    return documents


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 2:
        print(
            f"usage: {Path(sys.argv[0]).name} [CATALOG_PATH] [REPOSITORY_ROOT]",
            file=sys.stderr,
        )
        return 2

    root = Path(args[1] if len(args) == 2 else Path.cwd()).expanduser().resolve()
    catalog_path = Path(args[0]) if args else root / "docs/publication-catalog.json"

    try:
        documents = validate(catalog_path, root=root)
    except ValidationError as exc:
        print(f"validate_publication_catalog.py: {exc}", file=sys.stderr)
        return 1

    print(f"Publication catalog valid: {len(documents)} document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
