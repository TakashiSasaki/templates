#!/usr/bin/env python3
"""Run guided-navigation generators with the composition/policy provider contract."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

PROVIDER_ORDER = ("composition", "policy")
MODULES = {
    "graph": "scripts.generate_index_navigation",
    "locales": "scripts.generate_index_navigation_locales",
    "viewer": "scripts.generate_index_navigation_viewer",
    "locale-viewer": "scripts.generate_index_navigation_locale_viewer",
}

# Several preserved navigation modules import provider-sensitive helpers by
# reference. Patching only the command module therefore does not change the
# defining module globals used by those helpers. Keep the dependency set
# explicit so every entry point receives one coherent provider contract.
PATCH_MODULES = {
    "graph": (
        "scripts.generate_index_navigation_base",
        "scripts.generate_index_navigation",
    ),
    "locales": (
        "scripts.generate_index_navigation_base",
        "scripts.generate_index_navigation",
        "scripts.generate_index_navigation_locales",
    ),
    "viewer": (
        "scripts.generate_index_navigation_base",
        "scripts.generate_index_navigation",
        "scripts.generate_index_navigation_viewer",
    ),
    "locale-viewer": (
        "scripts.generate_index_navigation_base",
        "scripts.generate_index_navigation",
        "scripts.generate_index_navigation_viewer",
        "scripts.generate_index_navigation_locale_viewer",
    ),
}


def _patch_module(module: ModuleType) -> None:
    if hasattr(module, "PROVIDER_ORDER"):
        module.PROVIDER_ORDER = PROVIDER_ORDER
    base = getattr(module, "_base", None)
    if base is not None and hasattr(base, "PROVIDER_ORDER"):
        base.PROVIDER_ORDER = PROVIDER_ORDER


def load_command(command: str) -> ModuleType:
    """Import a command and apply the provider contract to its defining modules."""
    loaded: dict[str, ModuleType] = {}
    for module_name in PATCH_MODULES[command]:
        module = importlib.import_module(module_name)
        _patch_module(module)
        loaded[module_name] = module
    return loaded[MODULES[command]]


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in MODULES:
        choices = ", ".join(MODULES)
        print(f"usage: {sys.argv[0]} <{choices}> [arguments...]", file=sys.stderr)
        return 2

    repository_root = Path(__file__).resolve().parents[1]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    command = sys.argv[1]
    module = load_command(command)
    sys.argv = [MODULES[command], *sys.argv[2:]]
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
