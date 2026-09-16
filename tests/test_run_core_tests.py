from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_core_tests import (
    BROWSER_INTEGRATION_MODULES,
    PROVIDER_INTEGRATION_MODULES,
    classify_test_modules,
    load_test_suite,
    run_tests,
)


class RunCoreTestsContractTests(unittest.TestCase):
    def test_all_modules_classified_without_overlap(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        all_modules = sorted([f.stem for f in tests_dir.glob("test_*.py")])
        classification = classify_test_modules(tests_dir)

        core_set = set(classification["core"])
        provider_set = set(classification["provider"])
        browser_set = set(classification["browser"])

        self.assertEqual(provider_set, PROVIDER_INTEGRATION_MODULES)
        self.assertEqual(browser_set, BROWSER_INTEGRATION_MODULES)
        self.assertTrue(core_set.isdisjoint(provider_set))
        self.assertTrue(core_set.isdisjoint(browser_set))
        self.assertTrue(provider_set.isdisjoint(browser_set))

        reconstructed = sorted(list(core_set | provider_set | browser_set))
        self.assertEqual(all_modules, reconstructed)
        self.assertGreaterEqual(len(core_set), 100)  # Retained post-cutover consumer/UI module floor.
        self.assertIn("test_publication_bundle", core_set)
        self.assertIn("test_stale_translation_reader", core_set)
        self.assertIn("test_integration_boundary", core_set)

    def test_core_and_integration_preserve_discovery_case_union(self) -> None:
        def ids(suite):
            result = []
            for child in suite:
                result.extend(ids(child) if isinstance(child, unittest.TestSuite) else [child.id()])
            return result
        core = ids(load_test_suite("core"))
        integration = ids(load_test_suite("integration"))
        discovered = ids(unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent)))
        self.assertFalse(set(core) & set(integration))
        self.assertCountEqual(core + integration, discovered)
        self.assertFalse(PROVIDER_INTEGRATION_MODULES)
        self.assertFalse(any('test_exact_checked_out_provider_descriptors' in name for name in core))

    def test_missing_integration_prerequisite_is_failure(self) -> None:
        class Missing(unittest.TestCase):
            def runTest(self):
                self.skipTest("provider absent")
        with patch('scripts.run_core_tests.load_test_suite', return_value=unittest.TestSuite([Missing()])), patch('sys.stderr', io.StringIO()):
            self.assertEqual(run_tests('integration'), 1)

    def test_load_core_test_suite_succeeds(self) -> None:
        suite = load_test_suite("core")
        self.assertGreaterEqual(suite.countTestCases(), 760)  # Post-cutover baseline: 767 retained cases.

    def test_doc_contract_breakage_fails_core_validation(self) -> None:
        """Regression test: broken reader/documentation contract must fail core validation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            failing_test = tmp_path / "test_broken_reader_contract.py"
            failing_test.write_text(
                "import unittest\n\n"
                "class BrokenDocContractTest(unittest.TestCase):\n"
                "    def test_reader_projection_contract(self):\n"
                "        self.fail('Reader projection contract violated in lightweight path')\n",
                encoding="utf-8",
            )
            # Running tests in this temp dir must return exit code 1
            stderr_buf = io.StringIO()
            with patch("sys.stderr", stderr_buf):
                exit_code = run_tests(suite_name="core", verbosity=0, tests_dir=tmp_path)
            self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
