#!/usr/bin/env python3
"""Regression test for repository-root-relative catalog path resolution."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from validate_publication_catalog import validate


def run() -> int:
    original_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory(prefix="publication-root-") as root_directory:
            root = Path(root_directory)
            (root / "docs").mkdir()
            (root / "README.md").write_text("# Overview\n", encoding="utf-8")
            (root / "docs/publication-catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "documents": [
                            {
                                "id": "overview",
                                "source": "README.md",
                                "optional": False,
                                "home": True,
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with tempfile.TemporaryDirectory(prefix="publication-cwd-") as cwd_directory:
                os.chdir(cwd_directory)
                documents = validate("docs/publication-catalog.json", root=root)

            if [document.id for document in documents] != ["overview"]:
                print("relative catalog path resolved to unexpected documents", file=sys.stderr)
                return 1
    except Exception as exc:  # noqa: BLE001 - report the complete regression failure.
        print(f"repository-root-relative catalog resolution failed: {exc}", file=sys.stderr)
        return 1
    finally:
        os.chdir(original_cwd)

    print("Publication catalog root-resolution test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
