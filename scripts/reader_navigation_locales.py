#!/usr/bin/env python3
"""Temporary CLI/API compatibility adapter; implementation belongs to Integration."""
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration import reader_navigation_locales as _implementation
if __name__ == "__main__":
    entrypoint = getattr(_implementation, 'main', None)
    if entrypoint is not None:
        raise SystemExit(entrypoint())
else:
    sys.modules[__name__] = _implementation
    globals().update({key: value for key, value in vars(_implementation).items()
                      if not key.startswith("__")})
