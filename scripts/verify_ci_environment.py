from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

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
            f"{lock_path}: local project distribution {project_name} must not be "
            "duplicated in the lock"
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


def validate_editable_direct_url(
    direct_url_text: str | None,
    project_root: Path = ROOT,
) -> tuple[str, ...]:
    if not direct_url_text:
        return ("local project distribution is missing direct_url.json",)

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError as exc:
        return (f"local project direct_url.json is invalid JSON: {exc}",)
    if not isinstance(direct_url, dict):
        return ("local project direct_url.json must contain an object",)

    directory_info = direct_url.get("dir_info")
    if not isinstance(directory_info, dict) or directory_info.get("editable") is not True:
        return ("local project distribution is not marked editable in direct_url.json",)

    raw_url = direct_url.get("url")
    if not isinstance(raw_url, str) or not raw_url:
        return ("local project direct_url.json is missing its source URL",)
    parsed = urlsplit(raw_url)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return ("local project editable source URL must be a local file URL",)

    source_path = Path(url2pathname(unquote(parsed.path))).resolve()
    expected_path = project_root.resolve()
    if source_path != expected_path:
        return (
            "local project editable source does not resolve to repository root: "
            f"expected {expected_path}, got {source_path}",
        )

    return ()


def editable_install_errors(
    project_name: str,
    project_root: Path = ROOT,
) -> tuple[str, ...]:
    try:
        distribution = metadata.distribution(project_name)
    except metadata.PackageNotFoundError:
        return (f"local project distribution is not installed: {project_name}",)
    return validate_editable_direct_url(
        distribution.read_text("direct_url.json"),
        project_root,
    )


def main() -> int:
    try:
        expected = expected_distribution_set()
        installed = installed_distribution_set()
        project_name, _project_version = load_local_project()
        errors = list(compare_distribution_sets(expected, installed))
        errors.extend(editable_install_errors(project_name))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Policy CI environment verification failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"Policy CI environment verification failed: {error}", file=sys.stderr)
        return 1

    print(
        "Installed distribution set matches requirements-ci.lock plus the local "
        "editable agent-policy project."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
