from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from scripts.verify_ci_environment import (
    compare_distribution_sets,
    installed_distribution_set,
    load_locked_requirements,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "requirements-docs.lock"


def expected_docs_distribution_set(
    lock_path: Path = DEFAULT_LOCK,
) -> dict[str, str]:
    return load_locked_requirements(lock_path)


def compare_docs_distribution_sets(
    expected: Mapping[str, str],
    installed: Mapping[str, str],
) -> tuple[str, ...]:
    return tuple(
        error.replace(
            "outside the lock and local project",
            "outside the documentation lock",
        )
        for error in compare_distribution_sets(expected, installed)
    )


def main() -> int:
    try:
        expected = expected_docs_distribution_set()
        installed = installed_distribution_set()
        errors = compare_docs_distribution_sets(expected, installed)
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            f"Policy documentation environment verification failed: {exc}",
            file=sys.stderr,
        )
        return 1

    if errors:
        for error in errors:
            print(
                f"Policy documentation environment verification failed: {error}",
                file=sys.stderr,
            )
        return 1

    print(
        "Installed distribution set matches requirements-docs.lock, excluding "
        "only the virtual environment's bootstrap pip."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
