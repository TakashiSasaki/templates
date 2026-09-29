#!/usr/bin/env python3
"""Check generated catalogs, publication exports and all local semantic tests."""
from pathlib import Path
import sys
import unittest
import catalog
import publication_export


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        records, collections = catalog.project(root, check=True)
        publication_export.validate(root)
    except (catalog.CatalogError, publication_export.ExportError, OSError, ValueError) as exc:
        print(f'Modeling validation failed: {exc}', file=sys.stderr)
        return 1
    print(f'Validated {records} records and {collections} collections')
    suite = unittest.TestLoader().discover(str(root/'tests'))
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
