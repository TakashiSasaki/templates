from __future__ import annotations

import re
import sys
import tomllib
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "requirements-runtime.lock"
DEFAULT_PYPROJECT = ROOT / "pyproject.toml"
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})
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
    actual_project_version = normalized_installed.get(normalized_project)
    if actual_project_version is None:
        errors.append(f"local project distribution is missing: {normalized_project}")
    elif actual_project_version != project_version:
        errors.append(
            "local project version mismatch: "
            f"expected {project_version}, installed {actual_project_version}"
        )

    unexpected = sorted(
        name
        for name in normalized_installed
        if name not in BOOTSTRAP_DISTRIBUTIONS
        and name != normalized_project
        and name not in normalized_locked
    )
    if unexpected:
        rendered = ", ".join(
            f"{name}=={normalized_installed[name]}" for name in unexpected
        )
        errors.append("installed runtime dependencies missing from lock: " + rendered)

    mismatched = sorted(
        name
        for name in set(normalized_locked) & set(normalized_installed)
        if normalized_locked[name] != normalized_installed[name]
    )
    if mismatched:
        rendered = ", ".join(
            f"{name}: expected {normalized_locked[name]}, installed {normalized_installed[name]}"
            for name in mismatched
        )
        errors.append("runtime dependency version mismatches: " + rendered)

    return tuple(errors)


def main() -> int:
    try:
        locked = load_locked_requirements()
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
        "Installed agent-policy runtime is constrained by requirements-runtime.lock "
        "and contains no unlocked runtime distributions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
