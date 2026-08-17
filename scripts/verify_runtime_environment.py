from __future__ import annotations

import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if __package__:
    from .verify_ci_environment import (
        installed_distribution_set,
        load_locked_requirements,
        normalize_distribution_name,
    )
else:
    # ``python -I path/to/script.py`` intentionally omits the script directory
    # from sys.path. Re-add only this reviewed repository-local directory so the
    # runtime verifier can reuse the CI verifier's distribution helpers without
    # re-enabling user or environment-controlled import paths.
    sys.path.insert(0, str(SCRIPT_DIR))
    from verify_ci_environment import (
        installed_distribution_set,
        load_locked_requirements,
        normalize_distribution_name,
    )

ROOT = SCRIPT_DIR.parent
DEFAULT_LOCK = ROOT / "requirements-runtime.lock"
DEFAULT_PYPROJECT = ROOT / "pyproject.toml"
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})


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


def compare_distribution_sets(
    locked: Mapping[str, str],
    installed: Mapping[str, str],
    *,
    project_name: str,
    project_version: str,
) -> tuple[str, ...]:
    normalized_locked = {
        normalize_distribution_name(name): version for name, version in locked.items()
    }
    normalized_installed = {
        normalize_distribution_name(name): version for name, version in installed.items()
    }
    normalized_project = normalize_distribution_name(project_name)

    errors: list[str] = []
    if normalized_project in normalized_locked:
        errors.append(
            "runtime lock must not contain the local project distribution: "
            f"{normalized_project}"
        )
        normalized_locked = {
            name: version
            for name, version in normalized_locked.items()
            if name != normalized_project
        }

    actual_project_version = normalized_installed.get(normalized_project)
    if actual_project_version is None:
        errors.append(f"local project distribution is missing: {normalized_project}")
    elif actual_project_version != project_version:
        errors.append(
            "local project version mismatch: "
            f"expected {project_version}, installed {actual_project_version}"
        )

    checked_installed = {
        name: version
        for name, version in normalized_installed.items()
        if name not in BOOTSTRAP_DISTRIBUTIONS and name != normalized_project
    }

    missing = sorted(set(normalized_locked) - set(checked_installed))
    if missing:
        errors.append("missing locked runtime distributions: " + ", ".join(missing))

    unexpected = sorted(set(checked_installed) - set(normalized_locked))
    if unexpected:
        rendered = ", ".join(
            f"{name}=={checked_installed[name]}" for name in unexpected
        )
        errors.append("installed runtime distributions missing from lock: " + rendered)

    mismatched = sorted(
        name
        for name in set(normalized_locked) & set(checked_installed)
        if normalized_locked[name] != checked_installed[name]
    )
    if mismatched:
        rendered = ", ".join(
            f"{name}: expected {normalized_locked[name]}, installed {checked_installed[name]}"
            for name in mismatched
        )
        errors.append("runtime dependency version mismatches: " + rendered)

    return tuple(errors)


def main() -> int:
    try:
        locked = load_locked_requirements(DEFAULT_LOCK)
        project_name, project_version = load_local_project()
        installed = installed_distribution_set()
        errors = compare_distribution_sets(
            locked,
            installed,
            project_name=project_name,
            project_version=project_version,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Runtime distribution verification failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"Runtime distribution verification failed: {error}", file=sys.stderr)
        return 1

    print(
        "Installed distribution set matches requirements-runtime.lock plus the "
        "local agent-policy project."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
