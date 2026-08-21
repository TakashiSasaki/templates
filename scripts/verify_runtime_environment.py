#!/usr/bin/env python3
"""Verify that the active interpreter matches the Composer consumer runtime contract."""

from __future__ import annotations

import importlib.metadata
import re
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOCK = SOURCE_ROOT / "requirements-runtime.lock"
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*===([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
SUPPORTED_MIN = (3, 11)
SUPPORTED_MAX_EXCLUSIVE = (3, 15)


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if EXACT_REQUIREMENT.fullmatch(value) is None:
            raise RuntimeError(
                f"{path.name}:{line_number}: runtime lock entry must be exact name===version"
            )
        name, version = value.split("===", 1)
        normalized = normalize_distribution_name(name)
        if normalized in requirements:
            raise RuntimeError(f"{path.name}: duplicate distribution {name!r}")
        requirements[normalized] = version
    if not requirements:
        raise RuntimeError(f"{path.name}: runtime lock must not be empty")
    return requirements


def installed_distributions() -> dict[str, str]:
    result: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            raise RuntimeError("installed distribution is missing Name metadata")
        normalized = normalize_distribution_name(name)
        if normalized in result:
            raise RuntimeError(f"duplicate installed distribution metadata for {name!r}")
        result[normalized] = distribution.version
    return result


def main() -> int:
    if sys.implementation.name != "cpython":
        raise RuntimeError("Composer consumer runtime requires CPython")
    version = sys.version_info[:2]
    if not (SUPPORTED_MIN <= version < SUPPORTED_MAX_EXCLUSIVE):
        raise RuntimeError(
            "unsupported CPython version: "
            f"{version[0]}.{version[1]}; supported versions are 3.11 through 3.14"
        )

    expected = parse_lock(RUNTIME_LOCK)
    installed = installed_distributions()
    checked = {
        name: version
        for name, version in installed.items()
        if name not in BOOTSTRAP_DISTRIBUTIONS
    }
    if checked != expected:
        missing = sorted(set(expected) - set(checked))
        unexpected = sorted(set(checked) - set(expected))
        mismatched = sorted(
            name
            for name in set(expected) & set(checked)
            if expected[name] != checked[name]
        )
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        if mismatched:
            details.append(
                "version-mismatch="
                + ",".join(
                    f"{name}:{checked[name]}!={expected[name]}" for name in mismatched
                )
            )
        raise RuntimeError(
            "installed distribution set does not match requirements-runtime.lock"
            + (": " + "; ".join(details) if details else "")
        )

    print(
        "Composer consumer runtime verified: "
        f"CPython {version[0]}.{version[1]}, {len(expected)} locked distributions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
