#!/usr/bin/env python3
"""Check Python imports against the requirements used by Site CI environments.

This is intentionally a bounded static contract.  It follows imports in the
declared CI entrypoints and repository-owned modules, but never imports the
application, installs packages, contacts a package index, or tries to model
Python packaging in general.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import warnings


@dataclass(frozen=True)
class PythonEnvironment:
    """A Site execution environment and its actual Python entrypoints."""

    name: str
    requirements: str
    entrypoints: tuple[str, ...]
    # Some environments execute repository tests in addition to their
    # production entrypoints. Test modules are inspected at module-import
    # depth so browser-only lazy imports do not leak into the build contract.
    shallow_entrypoints: tuple[str, ...] = ()
    include_nested_imports: bool = True
    required_distributions: tuple[str, ...] = ()


CORE_ENTRYPOINTS = (
    "scripts/run_core_tests.py",
)

# ``run_core_tests.py`` dynamically imports the complete test inventory. The
# modules themselves are still entrypoints, but their lazy browser imports are
# owned by the visual environment rather than requirements.txt.
TEST_ENTRYPOINTS = ("tests/test_*.py",)

BUILD_ENTRYPOINTS = (
    "scripts/acquire_integration_bundle.py",
    "scripts/resolve_site_checkout.py",
    "scripts/site_build_artifact.py",
    "scripts/run_core_tests.py",
    "scripts/render_publication_bundle.py",
    "scripts/prepare_site_metadata.py",
    "scripts/generate_glossary_viewer.py",
    "scripts/finalize_site_metadata.py",
    "scripts/render_website_metadata.py",
    "scripts/finalize_translation_reader.py",
    "scripts/validate_translation_pairs.py",
    "scripts/finalize_guided_locales.py",
    "scripts/finalize_glossary_annotations.py",
    "scripts/check_public_url_boundary.py",
    "scripts/validate_site_links.py",
    "scripts/check_audience_artifact.py",
    "scripts/check_bundle_reader.py",
    "scripts/check_site_artifact.py",
    "site_renderer/**/*.py",
    "publication_bundle/**/*.py",
    "ci_artifacts/**/*.py",
)

VISUAL_ENTRYPOINTS = (
    "scripts/acquire_integration_bundle.py",
    "scripts/consume_site_build_artifact.py",
    "scripts/check_audience_artifact.py",
    "scripts/check_audience_runtime.py",
    "scripts/check_search_history.py",
    "scripts/check_search_history_review_regressions.py",
    "scripts/check_pwa_freshness.py",
    "scripts/check_pwa_locale_chrome.py",
    "scripts/check_pwa_commit_regressions.py",
    "scripts/check_pwa_capabilities.py",
    "scripts/check_pwa_slow_convergence.py",
    "scripts/check_mobile_layout.py",
    "scripts/check_glossary_locale_chrome.py",
    "scripts/check_stale_translation_runtime.py",
    "scripts/check_reference_website.py",
    "scripts/check_reference_pwa.py",
    "scripts/render_reference_consumer.py",
    "scripts/check_composition_playground_browser.py",
    "scripts/check_composition_playground_final_browser.py",
    "scripts/check_composition_playground_final_three_browser.py",
    "scripts/check_composition_playground_final_grid_browser.py",
    "scripts/check_composition_playground_cross_authority.py",
    "scripts/check_composition_playground_webmcp_browser.py",
    "scripts/check_composition_playground_latest_five_browser.py",
)

COMPOSITION_ENTRYPOINTS = (
    ".template-composition/validate.py",
    ".template-composition/validate_impl.py",
    ".template-composition/validators/*.py",
)

ENVIRONMENTS = (
    PythonEnvironment(
        "core",
        "requirements.txt",
        CORE_ENTRYPOINTS,
        shallow_entrypoints=TEST_ENTRYPOINTS,
    ),
    PythonEnvironment(
        "build",
        "requirements-build.lock",
        BUILD_ENTRYPOINTS,
        shallow_entrypoints=TEST_ENTRYPOINTS,
        required_distributions=("zensical",),
    ),
    PythonEnvironment(
        "visual",
        "requirements-visual.txt",
        VISUAL_ENTRYPOINTS,
        required_distributions=("playwright",),
    ),
    PythonEnvironment(
        "composition-validation",
        ".template-composition/requirements-validation.lock",
        COMPOSITION_ENTRYPOINTS,
    ),
)
ENVIRONMENT_NAMES = tuple(environment.name for environment in ENVIRONMENTS)

# Import names and distribution names are usually identical. Keep exceptions
# explicit and small rather than introducing a package metadata dependency.
IMPORT_DISTRIBUTION_OVERRIDES = {
    "yaml": "PyYAML",
    "pymdownx": "pymdown-extensions",
}

try:
    STDLIB_MODULES = frozenset(sys.stdlib_module_names)
except AttributeError:  # pragma: no cover - supported Python versions expose it
    STDLIB_MODULES = frozenset(
        {
            "argparse",
            "ast",
            "asyncio",
            "base64",
            "collections",
            "contextlib",
            "dataclasses",
            "datetime",
            "functools",
            "gzip",
            "hashlib",
            "html",
            "http",
            "importlib",
            "io",
            "ipaddress",
            "itertools",
            "json",
            "math",
            "os",
            "pathlib",
            "platform",
            "re",
            "shutil",
            "sqlite3",
            "string",
            "subprocess",
            "sys",
            "tarfile",
            "tempfile",
            "threading",
            "time",
            "tomllib",
            "types",
            "typing",
            "unicodedata",
            "unittest",
            "urllib",
            "uuid",
            "xml",
            "zipfile",
        }
    )

REQUIREMENT_NAME = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^]]+\])?\s*(?:(?:===|==|~=|!=|>=|<=|>|<).*)?$"
)
VERSION_OPERATOR = re.compile(r"\s*(?:===|==|~=|!=|>=|<=|>|<)")


@dataclass(frozen=True)
class ImportReference:
    module: str
    level: int = 0


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, include_nested_imports: bool) -> None:
        self.include_nested_imports = include_nested_imports
        self.references: list[ImportReference] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.references.extend(ImportReference(alias.name) for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        self.references.append(ImportReference(module, node.level))
        # ``from site_renderer import guided`` and equivalent package imports
        # need their submodule followed as a first-party dependency.
        if module:
            self.references.extend(
                ImportReference(f"{module}.{alias.name}", node.level)
                for alias in node.names
                if alias.name != "*"
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self.include_nested_imports:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self.include_nested_imports:
            self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self.include_nested_imports:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        if self.include_nested_imports:
            self.generic_visit(node)


def normalize_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _entrypoint_paths(
    root: Path,
    environment: PythonEnvironment,
    patterns: tuple[str, ...] | None = None,
) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    errors: list[str] = []
    for pattern in patterns if patterns is not None else environment.entrypoints:
        if any(character in pattern for character in "*?["):
            matches = sorted(path for path in root.glob(pattern) if path.is_file())
            if not matches:
                errors.append(
                    f"{environment.name}: entrypoint pattern matched no files: {pattern}"
                )
            paths.extend(matches)
            continue
        path = root / pattern
        if not path.is_file():
            errors.append(f"{environment.name}: entrypoint is unavailable: {pattern}")
        else:
            paths.append(path)
    return list(dict.fromkeys(paths)), errors


def _search_roots(root: Path) -> tuple[Path, ...]:
    return (
        root,
        root / "scripts",
        root / "site_renderer",
        root / "publication_bundle",
        root / "ci_artifacts",
        root / ".template-composition",
        root / ".template-composition" / "validators",
        root / "tests",
    )


def _module_path(root: Path, module: str) -> Path | None:
    if not module or any(part in {"", ".", ".."} for part in module.split(".")):
        return None
    relative = Path(*module.split("."))
    for search_root in _search_roots(root):
        file_path = search_root / relative.with_suffix(".py")
        if file_path.is_file():
            return file_path
        package_init = search_root / relative / "__init__.py"
        if package_init.is_file():
            return package_init
    return None


def _first_party_namespace(root: Path, name: str) -> bool:
    """Recognize namespace/package roots used by scripts executed by path."""

    return any(
        (search_root / name).is_dir() or (search_root / f"{name}.py").is_file()
        for search_root in _search_roots(root)
    )


def _resolve_reference(root: Path, source: Path, reference: ImportReference) -> Path | None:
    module = reference.module
    if reference.level:
        try:
            relative_source = source.relative_to(root)
        except ValueError:
            return None
        package = relative_source.parent.parts
        if reference.level > len(package) + 1:
            return None
        package = package[: len(package) - reference.level + 1]
        module = ".".join((*package, *(module.split(".") if module else ())))
    return _module_path(root, module)


def _parse_imports(path: Path, include_nested_imports: bool) -> tuple[tuple[ImportReference, ...], str | None]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return (), str(exc)
    visitor = _ImportVisitor(include_nested_imports)
    visitor.visit(tree)
    return tuple(visitor.references), None


def _requirements(root: Path, relative: str) -> tuple[dict[str, str], list[str]]:
    path = root / relative
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return {}, [f"cannot read {relative}: {exc}"]
    distributions: dict[str, str] = {}
    errors: list[str] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = REQUIREMENT_NAME.fullmatch(line)
        if match is None:
            errors.append(f"{relative}:{line_number}: cannot parse requirement {raw_line!r}")
            continue
        name = match.group(1)
        distributions[normalize_distribution(name)] = name
    return distributions, errors


def _external_distributions(
    root: Path,
    entrypoints: list[Path],
    include_nested_imports: bool,
) -> tuple[set[str], list[str]]:
    pending = list(entrypoints)
    visited: set[Path] = set()
    distributions: set[str] = set()
    errors: list[str] = []
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        references, parse_error = _parse_imports(path, include_nested_imports)
        if parse_error is not None:
            errors.append(f"cannot parse {path.relative_to(root)}: {parse_error}")
            continue
        for reference in references:
            first_party = _resolve_reference(root, path, reference)
            if first_party is not None:
                pending.append(first_party)
                continue
            top_level = reference.module.split(".", 1)[0]
            if (
                not top_level
                or top_level in STDLIB_MODULES
                or _first_party_namespace(root, top_level)
            ):
                continue
            distributions.add(
                IMPORT_DISTRIBUTION_OVERRIDES.get(top_level, top_level)
            )
    return distributions, errors


def validate_environment(
    root: Path,
    environment: PythonEnvironment,
    *,
    requirements_path: Path | None = None,
) -> list[str]:
    """Return static dependency-contract errors for one CI environment."""

    entrypoints, errors = _entrypoint_paths(root, environment)
    shallow_entrypoints, shallow_errors = _entrypoint_paths(
        root, environment, environment.shallow_entrypoints
    )
    errors.extend(shallow_errors)
    required, import_errors = _external_distributions(
        root, entrypoints, environment.include_nested_imports
    )
    errors.extend(import_errors)
    if shallow_entrypoints:
        shallow_required, shallow_import_errors = _external_distributions(
            root, shallow_entrypoints, include_nested_imports=False
        )
        required.update(shallow_required)
        errors.extend(shallow_import_errors)
    required.update(environment.required_distributions)
    requirement_file = requirements_path or (root / environment.requirements)
    if requirements_path is not None:
        try:
            relative = requirement_file.relative_to(root).as_posix()
        except ValueError:
            relative = str(requirement_file)
        declared, requirement_errors = _requirements(requirement_file.parent, requirement_file.name)
    else:
        relative = environment.requirements
        declared, requirement_errors = _requirements(root, environment.requirements)
    errors.extend(f"{environment.name}: {error}" for error in requirement_errors)
    missing = sorted(
        distribution
        for distribution in required
        if normalize_distribution(distribution) not in declared
    )
    if missing:
        errors.append(
            f"{environment.name}: {relative} is missing distributions required by "
            f"its Python entrypoints: {', '.join(missing)}"
        )
    return errors


def environment_by_name(name: str) -> PythonEnvironment:
    for environment in ENVIRONMENTS:
        if environment.name == name:
            return environment
    raise KeyError(name)


def validate(root: Path, names: tuple[str, ...] | None = None) -> list[str]:
    selected = (
        ENVIRONMENTS
        if names is None
        else tuple(environment_by_name(name) for name in names)
    )
    errors: list[str] = []
    for environment in selected:
        errors.extend(validate_environment(root, environment))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument(
        "--environment",
        action="append",
        choices=ENVIRONMENT_NAMES,
        help="check only this environment; repeat to select multiple environments",
    )
    args = parser.parse_args()
    errors = validate(
        Path(args.root).resolve(), tuple(args.environment) if args.environment else None
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    selected = ", ".join(args.environment) if args.environment else ", ".join(ENVIRONMENT_NAMES)
    print(f"Python dependency boundaries ({selected}): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
