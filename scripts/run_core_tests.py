#!/usr/bin/env python3
"""L1 core repository test runner and classification boundary.

Classifies and executes repository unit and contract tests according to the staged CI model:
- L1 Core Validation: Pure repository-owned unit and contract tests (Markdown contracts,
  reader projections, authority models, navigation graphs, glossary contracts, translation
  manifests, site links, public URL boundaries, workflow boundaries, and classifiers).
  Executes without external provider checkouts or external browser binaries.
- L2 Integration: Provider-dependent tests (requiring checked-out and materialized
  composition/policy providers) and browser/node-dependent integration tests.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

# Tests that strictly require checked-out and materialized external provider checkouts.
PROVIDER_INTEGRATION_MODULES = frozenset(
    {
        "test_catalog_architecture_translation_integration",
        "test_composer_mvp_translation_integration",
        "test_composition_model_translation_integration",
        "test_composition_translation_reader_integration",
        "test_generated_contract_manifest_translation_integration",
        "test_glossary_locked_providers",
        "test_index_navigation_locked_providers",
    }
)

# Tests that strictly require Node.js or browser execution engines.
BROWSER_INTEGRATION_MODULES = frozenset(
    {
        "test_repository_browser_deep_links",
        "test_repository_browser_filter",
        "test_repository_browser_mobile",
        "test_repository_browser_modern_listener",
        "test_repository_browser_sharing",
    }
)


def get_default_tests_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "tests"


def classify_test_modules(
    tests_dir: Path | None = None,
) -> dict[str, list[str]]:
    if tests_dir is None:
        tests_dir = get_default_tests_dir()

    all_modules = sorted([f.stem for f in tests_dir.glob("test_*.py")])
    core = []
    provider = []
    browser = []

    for mod in all_modules:
        if mod in PROVIDER_INTEGRATION_MODULES:
            provider.append(mod)
        elif mod in BROWSER_INTEGRATION_MODULES:
            browser.append(mod)
        else:
            core.append(mod)

    return {
        "core": core,
        "provider": provider,
        "browser": browser,
    }


def load_test_suite(
    suite_name: str = "core",
    tests_dir: Path | None = None,
) -> unittest.TestSuite:
    if tests_dir is None:
        tests_dir = get_default_tests_dir()

    repo_root = tests_dir.parent
    for p in (str(tests_dir), str(repo_root)):
        if p not in sys.path:
            sys.path.insert(0, p)

    categories = classify_test_modules(tests_dir)
    if suite_name == "core":
        selected = categories["core"]
    elif suite_name == "provider":
        selected = categories["provider"]
    elif suite_name == "browser":
        selected = categories["browser"]
    elif suite_name == "all":
        selected = sorted(
            categories["core"] + categories["provider"] + categories["browser"]
        )
    else:
        raise ValueError(f"Unknown test suite: {suite_name!r}")

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for mod_name in selected:
        mod = __import__(mod_name)
        suite.addTests(loader.loadTestsFromModule(mod))
    return suite


def run_tests(
    suite_name: str = "core",
    verbosity: int = 1,
    tests_dir: Path | None = None,
) -> int:
    suite = load_test_suite(suite_name=suite_name, tests_dir=tests_dir)
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    if not result.wasSuccessful():
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=["core", "provider", "browser", "all"],
        default="core",
        help="Test suite boundary to execute (default: core)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List test module classifications and exit",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Run tests with higher verbosity",
    )
    args = parser.parse_args(argv)

    if args.list:
        classification = classify_test_modules()
        print("Test module classification:")
        for cat, mods in classification.items():
            print(f"  {cat} ({len(mods)} modules):")
            for m in mods:
                print(f"    - {m}")
        return 0

    return run_tests(
        suite_name=args.suite,
        verbosity=2 if args.verbose else 1,
    )


if __name__ == "__main__":
    raise SystemExit(main())
