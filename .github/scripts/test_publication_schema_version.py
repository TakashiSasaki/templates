#!/usr/bin/env python3
"""Verify that JSON numeric lookalikes do not satisfy schema_version."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from validate_publication_catalog import ValidationError, validate


def run() -> int:
    failures: list[str] = []

    for encoded, schema_version in (("1.0", 1.0), ("1e0", 1.0)):
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
                    f"schema_version {schema_version!r} ({encoded}): "
                    "validation unexpectedly succeeded"
                )
            except ValidationError as exc:
                expected = "schema_version must be 1 and use an integer JSON value"
                if expected not in str(exc):
                    failures.append(
                        f"schema_version {schema_version!r} ({encoded}): "
                        f"unexpected diagnostic {str(exc)!r}"
                    )
            except Exception as exc:  # noqa: BLE001 - record all harness failures.
                failures.append(
                    f"schema_version {schema_version!r} ({encoded}): "
                    f"unexpected {type(exc).__name__}: {exc}"
                )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Publication schema-version type tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
