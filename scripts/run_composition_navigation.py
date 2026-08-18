#!/usr/bin/env python3
"""Run guided-navigation generators with the composition/policy provider contract."""

from __future__ import annotations

import importlib
import sys

PROVIDER_ORDER = ("composition", "policy")
MODULES = {
    "graph": "scripts.generate_index_navigation",
    "locales": "scripts.generate_index_navigation_locales",
    "viewer": "scripts.generate_index_navigation_viewer",
    "locale-viewer": "scripts.generate_index_navigation_locale_viewer",
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in MODULES:
        choices = ", ".join(MODULES)
        print(f"usage: {sys.argv[0]} <{choices}> [arguments...]", file=sys.stderr)
        return 2
    command = sys.argv[1]
    module = importlib.import_module(MODULES[command])
    if hasattr(module, "PROVIDER_ORDER"):
        module.PROVIDER_ORDER = PROVIDER_ORDER
    base = getattr(module, "_base", None)
    if base is not None and hasattr(base, "PROVIDER_ORDER"):
        base.PROVIDER_ORDER = PROVIDER_ORDER
    sys.argv = [MODULES[command], *sys.argv[2:]]
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
