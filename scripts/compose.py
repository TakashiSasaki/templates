#!/usr/bin/env python3
"""Resolve, plan, materialize, inspect, and validate composition consumers."""

from composer_core import CompositionError, _assert_tracked_authority, main

__all__ = ["CompositionError", "_assert_tracked_authority", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
