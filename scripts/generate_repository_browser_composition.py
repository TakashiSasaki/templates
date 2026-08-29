#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical static repository browser."""

from __future__ import annotations

try:
    from scripts import generate_repository_browser as base
except ModuleNotFoundError:
    import generate_repository_browser as base


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
