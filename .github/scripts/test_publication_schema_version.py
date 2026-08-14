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

            try:
                validate(catalog_path, root=root)
                failures.append(
                    f"schema_version {encoded}: validation unexpectedly succeeded"
                )
            except ValidationError as exc:
                expected = "schema_version must be integer 1 or 3"
                if expected not in str(exc):
                    failures.append(
                        f"schema_version {encoded}: unexpected diagnostic {str(exc)!r}"
                    )
            except Exception as exc:  # noqa: BLE001 - record all harness failures.
                failures.append(
                    f"schema_version {encoded}: unexpected {type(exc).__name__}: {exc}"
                )

    for version, glossary in ((1, False), (3, True)):
        with tempfile.TemporaryDirectory(
            prefix="publication-schema-version-positive-"
        ) as directory:
            root = Path(directory)
            catalog_path = write_catalog(root, version, glossary=glossary)
            try:
                validate(catalog_path, root=root)
            except Exception as exc:  # noqa: BLE001 - record all harness failures.
                failures.append(
                    f"schema_version {version}: valid catalog failed: "
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
