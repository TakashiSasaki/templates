#!/usr/bin/env python3
"""Compatibility entry point for integrated audience data."""
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration import audience as _implementation
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
else:
    sys.modules[__name__] = _implementation
    globals().update({key: value for key, value in vars(_implementation).items() if not key.startswith("__")})
