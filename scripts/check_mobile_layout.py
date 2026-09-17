#!/usr/bin/env python3
"""Run deterministic Site layout checks."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts import check_mobile_layout_core as core
except ModuleNotFoundError:
    import check_mobile_layout_core as core


# Preserve the validator/test API historically exported by this entrypoint.
CASES = core.CASES
CheckCase = core.CheckCase
MobileLayoutError = core.MobileLayoutError
_number = core._number
_validate_cases = core._validate_cases
validate_metrics = core.validate_metrics
def run_checks(site_root: Path, output_root: Path) -> None:
    core.run_checks(site_root, output_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_checks(args.site_root.resolve(strict=True), args.output_root.resolve())
    except (OSError, MobileLayoutError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
