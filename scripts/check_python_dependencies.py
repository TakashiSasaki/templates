#!/usr/bin/env python3
"""Check bounded Policy Python entrypoint imports against environment locks."""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:===|==)([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
IMPORT_DISTRIBUTIONS = {
    "attr": "attrs",
    "attrs": "attrs",
    "jinja2": "Jinja2",
    "jsonschema": "jsonschema",
    "markdown": "Markdown",
    "markupsafe": "MarkupSafe",
    "packaging": "packaging",
    "pathspec": "pathspec",
    "pygments": "Pygments",
    "pytest": "pytest",
    "xdist": "pytest-xdist",
    "yaml": "PyYAML",
}


@dataclass(frozen=True)
class Environment:
    name: str
    requirements: str
    roots: tuple[str, ...]


ENVIRONMENTS = (
    Environment(
        "ci",
        "requirements-ci.lock",
        (
            "scripts/run_policy_preflight.py",
            "scripts/verify_ci_environment.py",
            "scripts/classify_policy_ci.py",
            "scripts/ci_change_classification.py",
            "tests",
        ),
    ),
    Environment(
        "runtime",
        "requirements-runtime.lock",
        (
            "src",
            "scripts/smoke_test_runtime_distribution.py",
        ),
    ),
    Environment(
        "release-verifier",
        "release/verifier-requirements.lock",
        (
            "scripts/verify-release-state.py",
            "scripts/verify_trusted_review_candidate.py",
            "scripts/plan_policy_release_chain.py",
        ),
    ),
)


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def read_requirements(path: Path) -> tuple[set[str], list[str]]:
    values: set[str] = set()
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return set(), [f"cannot read {path}: {exc}"]
    for line_number, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = REQUIREMENT.fullmatch(line)
        if match is None:
            errors.append(f"{path.name}:{line_number}: expected exact pinned requirement")
            continue
        name = normalize(match.group(1))
        if name in values:
            errors.append(f"{path.name}:{line_number}: duplicate distribution {name}")
        values.add(name)
    return values, errors


def _files(root: Path, patterns: tuple[str, ...]) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    errors: list[str] = []
    for pattern in patterns:
        candidate = root / pattern
        if candidate.is_dir():
            matches = sorted(candidate.rglob("*.py"))
        elif any(character in pattern for character in "*?["):
            matches = sorted(path for path in root.glob(pattern) if path.is_file())
        else:
            matches = [candidate] if candidate.is_file() else []
        if not matches:
            errors.append(f"entrypoint pattern matched no files: {pattern}")
        paths.extend(matches)
    return list(dict.fromkeys(paths)), errors


def _imports(paths: list[Path]) -> tuple[set[str], list[str]]:
    modules: set[str] = set()
    errors: list[str] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"cannot parse {path}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".", 1)[0])
    return modules, errors


def _local_modules(root: Path) -> set[str]:
    modules = {"agent_policy", "scripts", "tests", "release", "skills"}
    for directory in (root / "src", root / "scripts", root / "tests", root / "skills"):
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            modules.add(path.stem)
        for path in directory.rglob("__init__.py"):
            modules.add(path.parent.name)
    return modules


def validate_environment(
    root: Path,
    environment: Environment,
    *,
    requirements_path: Path | None = None,
) -> list[str]:
    requirements, errors = read_requirements(requirements_path or root / environment.requirements)
    paths, path_errors = _files(root, environment.roots)
    errors.extend(path_errors)
    modules, parse_errors = _imports(paths)
    errors.extend(parse_errors)
    stdlib = frozenset(getattr(sys, "stdlib_module_names", ()))
    local_modules = _local_modules(root)
    for module in sorted(modules):
        if module in stdlib or module in local_modules or module == "__future__":
            continue
        distribution = IMPORT_DISTRIBUTIONS.get(module)
        if distribution is None:
            errors.append(
                f"{environment.name}: no bounded distribution mapping for import {module}"
            )
            continue
        if normalize(distribution) not in requirements:
            errors.append(
                f"{environment.name}: import {module} requires undeclared distribution "
                f"{distribution}"
            )
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for environment in ENVIRONMENTS:
        errors.extend(validate_environment(root, environment))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Policy entrypoint dependency declarations: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
