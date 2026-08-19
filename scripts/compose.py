#!/usr/bin/env python3
"""Resolve, plan, materialize, inspect, and validate composition consumers."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from composer_core import CompositionError, _assert_tracked_authority, main

__all__ = ["CompositionError", "_assert_tracked_authority", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
