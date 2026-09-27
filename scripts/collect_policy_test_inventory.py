#!/usr/bin/env python3
"""Collect exact pytest node IDs without executing the tests."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest


class InventoryPlugin:
    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.collected = False

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        node_ids = [item.nodeid for item in session.items]
        self.destination.write_text(
            json.dumps(node_ids, indent=2) + "\n", encoding="utf-8"
        )
        self.collected = True


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(arguments)

    # Keep this collector safe when invoked directly as well as through the
    # canonical runner. pytest-xdist settings are always supplied explicitly.
    for name in tuple(os.environ):
        if name.startswith("PYTEST_"):
            del os.environ[name]

    plugin = InventoryPlugin(args.output)
    result = pytest.main(
        ["--collect-only", "-q", "--no-header", "--no-summary", "-o", "addopts="],
        plugins=[plugin],
    )
    if result != pytest.ExitCode.OK or not plugin.collected:
        args.output.unlink(missing_ok=True)
        return int(result or 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
