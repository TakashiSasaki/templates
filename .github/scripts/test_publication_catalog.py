#!/usr/bin/env python3
"""Regression tests for the publication catalog validator."""

from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
from pathlib import Path

from validate_publication_catalog import ValidationError, validate


BASE_DOCUMENTS = [
    {"id": "overview", "source": "README.md", "optional": False, "home": True},
    {"id": "guide", "source": "docs/guide.md", "optional": True, "home": False},
]


def prepare_repository() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory(prefix="publication-catalog-test-")
    root = Path(temporary.name)
    (root / "docs").mkdir()
    (root / "README.md").write_text("# Overview\n", encoding="utf-8")
    (root / "docs/guide.md").write_text("# Guide\n", encoding="utf-8")
    return temporary


def write_catalog(
    root: Path,
    *,
    documents: list[dict[str, object]] | None = None,
    schema_version: object = 1,
    extra: dict[str, object] | None = None,
) -> Path:
    catalog = {
        "schema_version": schema_version,
        "documents": copy.deepcopy(BASE_DOCUMENTS if documents is None else documents),
    }
    if extra:
        catalog.update(extra)
    path = root / "docs/publication-catalog.json"
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return path


def _mutated_catalog(root: Path, index: int, field: str, value: object) -> Path:
    documents = copy.deepcopy(BASE_DOCUMENTS)
    documents[index][field] = value
    return write_catalog(root, documents=documents)


def _write_invalid_utf8(root: Path) -> Path:
    path = write_catalog(root)
    path.write_bytes(path.read_bytes().replace(b"guide", b"guide\xff", 1))
    return path


def _write_non_markdown(root: Path) -> Path:
    (root / "docs/guide.txt").write_text("guide\n", encoding="utf-8")
    return _mutated_catalog(root, 1, "source", "docs/guide.txt")


def _write_symlinked_source(root: Path) -> Path:
    (root / "docs/guide.md").unlink()
    (root / "docs/guide.md").symlink_to(root / "README.md")
    return write_catalog(root)


def _set_all_home(root: Path, value: bool) -> Path:
    documents = copy.deepcopy(BASE_DOCUMENTS)
    for document in documents:
        document["home"] = value
    return write_catalog(root, documents=documents)


def _write_missing_home(root: Path) -> Path:
    documents = copy.deepcopy(BASE_DOCUMENTS)
    del documents[1]["home"]
    return write_catalog(root, documents=documents)


def run() -> int:
    failures: list[str] = []

    with prepare_repository() as directory:
        root = Path(directory)
        try:
            documents = validate(write_catalog(root), root=root)
            actual = [document.id for document in documents]
            expected = ["overview", "guide"]
            if actual != expected:
                failures.append(f"valid catalog: expected {expected!r}, got {actual!r}")
        except Exception as exc:  # noqa: BLE001 - record all harness failures.
            failures.append(f"valid catalog: unexpected {type(exc).__name__}: {exc}")

    invalid_cases = [
        (
            "rejects unsupported schema versions",
            r"schema_version must be integer 1 or 3",
            lambda root: write_catalog(root, schema_version=2),
        ),
        (
            "rejects unsupported root fields",
            r"unsupported: navigation",
            lambda root: write_catalog(root, extra={"navigation": []}),
        ),
        (
            "rejects malformed UTF-8 before JSON parsing",
            r"content is not valid UTF-8",
            _write_invalid_utf8,
        ),
        (
            "rejects duplicate document ids",
            r"Duplicate publication document id: overview",
            lambda root: _mutated_catalog(root, 1, "id", "overview"),
        ),
        (
            "rejects duplicate source paths",
            r"Duplicate publication document source: README\.md",
            lambda root: _mutated_catalog(root, 1, "source", "README.md"),
        ),
        (
            "rejects invalid document ids",
            r"lowercase kebab-case",
            lambda root: _mutated_catalog(root, 1, "id", "Guide_Page"),
        ),
        (
            "rejects unsafe parent traversal",
            r"safe relative POSIX path",
            lambda root: _mutated_catalog(root, 1, "source", "../guide.md"),
        ),
        (
            "rejects backslash paths",
            r"safe relative POSIX path",
            lambda root: _mutated_catalog(root, 1, "source", "docs\\guide.md"),
        ),
        (
            "rejects non-Markdown sources",
            r"must identify a Markdown file",
            _write_non_markdown,
        ),
        (
            "rejects missing source files",
            r"existing regular file",
            lambda root: _mutated_catalog(root, 1, "source", "docs/missing.md"),
        ),
        (
            "rejects symlinked source files",
            r"traverses a symlink",
            _write_symlinked_source,
        ),
        (
            "rejects catalogs without a home document",
            r"exactly one home document",
            lambda root: _set_all_home(root, False),
        ),
        (
            "rejects multiple home documents",
            r"exactly one home document",
            lambda root: _set_all_home(root, True),
        ),
        (
            "rejects an optional home document",
            r"home document must not be optional",
            lambda root: _mutated_catalog(root, 0, "optional", True),
        ),
        (
            "rejects non-boolean optional values",
            r"optional must be boolean",
            lambda root: _mutated_catalog(root, 1, "optional", "yes"),
        ),
        (
            "rejects missing document fields",
            r"missing: home",
            _write_missing_home,
        ),
    ]

    for name, pattern, mutate in invalid_cases:
        with prepare_repository() as directory:
            root = Path(directory)
            catalog_path = mutate(root)
            try:
                validate(catalog_path, root=root)
                failures.append(f"{name}: validation unexpectedly succeeded")
            except ValidationError as exc:
                if re.search(pattern, str(exc)) is None:
                    failures.append(f"{name}: unexpected diagnostic {str(exc)!r}")
            except Exception as exc:  # noqa: BLE001 - record all harness failures.
                failures.append(f"{name}: unexpected {type(exc).__name__}: {exc}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(f"Publication catalog tests passed ({len(invalid_cases) + 1} cases).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
