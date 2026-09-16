#!/usr/bin/env python3
"""Integration candidate qualification ends at the Publication Bundle boundary."""
import importlib.abc
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class IntegrationImportBoundary(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'site_renderer' or fullname.startswith(('site_renderer.', 'scripts.')):
            raise ImportError('Integration qualification cannot import Site implementation: ' + fullname)


if __name__ == '__main__':
    sys.meta_path.insert(0, IntegrationImportBoundary())
    from integration.producer import main
    from integration.qualification import qualify
    main(producer=qualify)
