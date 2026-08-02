from __future__ import annotations

import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "requirements-ci.lock"
DEFAULT_PYPROJECT = ROOT / "pyproject.toml"
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip"})
ARBITRARY_EXACT_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)===(?P<version>[A-Za-z0-9][A-Za-z0-9._+!-]*)$"
)


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_locked_requirements(path: Path = DEFAULT_LOCK) -> dict[str, str]:
    locked: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = ARBITRARY_EXACT_REQUIREMENT.fullmatch(line)
        if match is None:
            raise ValueError(
                f"{path}:{line_number}: expected an arbitrary-exact name===version entry"
            )

        name = normalize_distribution_name(match.group("name"))
        version = match.group("version")
        if name in locked:
            raise ValueError(f"{path}:{line_number}: duplicate distribution {name}")
        locked[name] = version

    return locked


def load_local_project(path: Path = DEFAULT_PYPROJECT) -> tuple[str, str]:
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    project = document.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"{path}: missing [project] table")

    raw_name = project.get("name")
    version = project.get("version")
    if not isinstance(raw_name, str) or not raw_name:
        raise ValueError(f"{path}: project.name must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{path}: project.version must be a non-empty string")

    return normalize_distribution_name(raw_name), version


def expected_distribution_set(
    lock_path: Path = DEFAULT_LOCK,
    pyproject_path: Path = DEFAULT_PYPROJECT,
) -> dict[str, str]:
    expected = load_locked_requirements(lock_path)
    project_name, project_version = load_local_project(pyproject_path)
    if project_name in expected:
        raise ValueError(
            f"{lock_path}: local project distribution {project_name} must not be duplicated in the lock"
        )
    expected[project_name] = project_version
    return expected


def installed_distribution_set() -> dict[str, str]:
    installed: dict[str, str] = {}
    for distribution in metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = normalize_distribution_name(raw_name)
        version = distribution.version
        previous = installed.get(name)
        if previous is not None and previous != version:
            raise RuntimeError(
                f"multiple installed versions reported for {name}: {previous}, {version}"
            )
        installed[name] = version
    return installed


def compare_distribution_sets(
    expected: Mapping[str, str], installed: Mapping[str, str]
) -> tuple[str, ...]:
    normalized_expected = {
        normalize_distribution_name(name): version for name, version in expected.items()
    }
    normalized_installed = {
        normalize_distribution_name(name): version for name, version in installed.items()
    }
    checked_installed = {
        name: version
        for name, version in normalized_installed.items()
        if name not in BOOTSTRAP_DISTRIBUTIONS
    }

    errors: list[str] = []
    missing = sorted(set(normalized_expected) - set(checked_installed))
    if missing:
        errors.append("missing expected distributions: " + ", ".join(missing))

    unexpected = sorted(set(checked_installed) - set(normalized_expected))
    if unexpected:
        rendered = ", ".join(
            f"{name}=={checked_installed[name]}" for name in unexpected
        )
        errors.append("unexpected distributions outside the lock and local project: " + rendered)

    mismatched = sorted(
        name
        for name in set(normalized_expected) & set(checked_installed)
        if normalized_expected[name] != checked_installed[name]
    )
    if mismatched:
        rendered = ", ".join(
            f"{name}: expected {normalized_expected[name]}, installed {checked_installed[name]}"
            for name in mismatched
        )
        errors.append("distribution version mismatches: " + rendered)

    return tuple(errors)


def main() -> int:
    try:
        expected = expected_distribution_set()
        installed = installed_distribution_set()
        errors = compare_distribution_sets(expected, installed)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Policy CI environment verification failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"Policy CI environment verification failed: {error}", file=sys.stderr)
        return 1

    print(
        "Installed distribution set matches requirements-ci.lock plus the local agent-policy project."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
