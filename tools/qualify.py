#!/usr/bin/env python3
"""Canonical local/CI qualification: current projections and all discovered tests."""
import json
import subprocess
from pathlib import Path
import sys
import unittest

import catalog
import publication_export


def check_progressive_discovery(root: Path) -> None:
    script = root / ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"
    result = subprocess.run([sys.executable, str(script), "--root", str(root), "--format", "json"],
                            capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"progressive discovery did not produce a report: {result.stderr}") from exc
    if result.returncode or report.get("result") != "NO_UPDATE_REQUIRED":
        raise ValueError(f"progressive discovery is not clean: {result.stdout}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        records, collections = catalog.project(root, check=True)
        publication_export.validate(root)
        check_progressive_discovery(root)
    except (catalog.CatalogError, publication_export.ExportError, OSError, UnicodeError, ValueError) as exc:
        print(f"Catalog qualification failed: {exc}", file=sys.stderr)
        return 1
    suite = unittest.TestLoader().discover(str(root / "tests"), pattern="test_*.py")
    count = suite.countTestCases()
    if count == 0:
        print("No tests discovered; refusing empty qualification", file=sys.stderr)
        return 1
    print(f"Qualifying {records} records, {collections} collections; {count} tests; Python {sys.version.split()[0]}", flush=True)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
