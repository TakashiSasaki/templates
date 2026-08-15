#!/usr/bin/env python3
"""Verify publication catalog schema-version typing and supported versions."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from validate_publication_catalog import ValidationError, validate


def write_catalog(root: Path, schema_version: object, glossary: bool = False) -> Path:
    (root / "docs").mkdir()
    (root / "README.md").write_text("# Overview\n", encoding="utf-8")
    catalog: dict[str, object] = {
        "schema_version": schema_version,
        "documents": [
            {
                "id": "overview",
                "source": "README.md",
                "optional": False,
                "home": True,
            }
        ],
    }
    if glossary:
        (root / "docs/glossary.yml").write_text(
            "schema_version: 1\nterms:\n  - id: templates-example\n"
            "    term: Example\n    origin: repository\n"
            "    definition: Example.\n",
            encoding="utf-8",
        )
        catalog["glossary"] = {"source": "docs/glossary.yml"}
    catalog_path = root / "docs/publication-catalog.json"
    catalog_path.write_text(json.dumps(catalog) + "\n", encoding="utf-8")
    return catalog_path


def assert_rejected(failures: list[str], root: Path, catalog_path: Path, label: str) -> None:
    try:
        validate(catalog_path, root=root)
        failures.append(f"schema_version {label}: validation unexpectedly succeeded")
    except ValidationError as exc:
        expected = "schema_version must be integer 3"
        if expected not in str(exc):
            failures.append(
                f"schema_version {label}: unexpected diagnostic {str(exc)!r}"
            )
    except Exception as exc:  # noqa: BLE001 - record all harness failures.
        failures.append(
            f"schema_version {label}: unexpected {type(exc).__name__}: {exc}"
        )


def run() -> int:
    failures: list[str] = []

    for encoded in ("1.0", "1e0", "3.0", "3e0"):
        with tempfile.TemporaryDirectory(
            prefix="publication-schema-version-test-"
        ) as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "README.md").write_text("# Overview\n", encoding="utf-8")
            catalog_path = root / "docs/publication-catalog.json"
            catalog_path.write_text(
                "{\"schema_version\":" + encoded + ",\"documents\":[{"
                "\"id\":\"overview\",\"source\":\"README.md\","
                "\"optional\":false,\"home\":true}]}\n",
                encoding="utf-8",
            )
            assert_rejected(failures, root, catalog_path, encoded)

    for version in (1, 2, 4, True, "3", 3.0, None, [3]):
        with tempfile.TemporaryDirectory(
            prefix="publication-schema-version-rejected-"
        ) as directory:
            root = Path(directory)
            catalog_path = write_catalog(root, version)
            assert_rejected(failures, root, catalog_path, repr(version))

    with tempfile.TemporaryDirectory(
        prefix="publication-schema-version-positive-"
    ) as directory:
        root = Path(directory)
        catalog_path = write_catalog(root, 3, glossary=True)
        try:
            validate(catalog_path, root=root)
        except Exception as exc:  # noqa: BLE001 - record all harness failures.
            failures.append(
                "schema_version 3: valid catalog failed: "
                f"{type(exc).__name__}: {exc}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Publication schema-version type tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
