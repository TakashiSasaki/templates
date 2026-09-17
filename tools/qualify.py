#!/usr/bin/env python3
"""Canonical local/CI qualification: current projections and all discovered tests."""
from pathlib import Path
import sys
import unittest

import catalog


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        records, collections = catalog.project(root, check=True)
    except (catalog.CatalogError, OSError, UnicodeError) as exc:
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
