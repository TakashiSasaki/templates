#!/usr/bin/env python3
"""One-shot test expectation alignment; removed by the repair commit."""
from pathlib import Path

OLD = "unsupported site manifest schema_version: 4"
NEW = "site manifest must be schema version 2 or 3"

for name in (
    "tests/test_site_website_contract_schema_version.py",
    "tests/test_repository_tree_manifest_schema_version.py",
):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count == 0:
        raise SystemExit(f"expected legacy error-message assertion missing: {name}")
    path.write_text(text.replace(OLD, NEW), encoding="utf-8")
