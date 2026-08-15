#!/usr/bin/env python3
"""Stable schema-v3 CLI alias for the canonical Site publication assembler."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.assemble_publications import AssemblyError, load_catalog, main

__all__ = ["AssemblyError", "load_catalog", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
