from __future__ import annotations

import hashlib
import unittest
from collections import Counter
from pathlib import Path

from scripts.run_unittest_shard import (
    REAL_BROWSER_TEST_IDS,
    TWO_SHARD_TIMING_OVERRIDES,
    discover_tests,
    select_tests_for_suite,
    shard_index_for_test_id,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


class UnittestShardTests(unittest.TestCase):
    def test_deterministic_assignment_maps_each_test_id_to_exactly_one_shard(self) -> None:
        test_ids = [
            f"test_example_{index}.ExampleTests.test_case_{index % 5}"
            for index in range(64)
        ]
        assignments = [shard_index_for_test_id(test_id, 2) for test_id in test_ids]
        self.assertEqual(assignments, [shard_index_for_test_id(test_id, 2) for test_id in test_ids])
        self.assertEqual(set(assignments), {0, 1})
        for test_id in test_ids:
            assigned = shard_index_for_test_id(test_id, 2)
            self.assertEqual(
                [index for index in range(2) if assigned == index],
                [assigned],
            )

    def test_two_shard_timing_overrides_are_narrow_and_do_not_change_other_counts(self) -> None:
        expected = {
            "test_composer_generated_material.ComposerGeneratedMaterialTests."
            "test_webapp_apply_generates_and_locks_contract_manifest",
            "test_webapp_auth_productization.WebappAuthenticationProductizationTests."
            "test_realistic_auth_fixture_reaches_transactional_release",
        }
        self.assertEqual(set(TWO_SHARD_TIMING_OVERRIDES), expected)
        self.assertEqual(set(TWO_SHARD_TIMING_OVERRIDES.values()), {1})

        for test_id in expected:
            digest = hashlib.sha256(test_id.encode("utf-8")).digest()
            pure_hash_two_shard = int.from_bytes(digest[:8], "big") % 2
            pure_hash_three_shard = int.from_bytes(digest[:8], "big") % 3
            self.assertEqual(pure_hash_two_shard, 0)
            self.assertEqual(shard_index_for_test_id(test_id, 2), 1)
            self.assertEqual(
                shard_index_for_test_id(test_id, 3),
                pure_hash_three_shard,
            )

    def test_duplicate_test_ids_keep_their_execution_multiplicity(self) -> None:
        duplicate_id = "test_duplicate.ExampleTests.test_case"
        assignments = [shard_index_for_test_id(duplicate_id, 2) for _ in range(3)]
        self.assertEqual(len(assignments), 3)
        self.assertEqual(len(set(assignments)), 1)

    def test_repository_discovery_has_unique_test_ids(self) -> None:
        discovered = discover_tests(ROOT / "tests", "test*.py")
        counts = Counter(test.id() for test in discovered)
        duplicates = {
            test_id: count
            for test_id, count in counts.items()
            if count > 1
        }
        self.assertEqual(duplicates, {})

    def test_named_suites_form_an_exact_partition_of_repository_discovery(self) -> None:
        discovered = discover_tests(ROOT / "tests", "test*.py")
        all_tests = select_tests_for_suite(discovered, "all")
        core_tests = select_tests_for_suite(discovered, "core")
        browser_tests = select_tests_for_suite(discovered, "real-browser")

        all_ids = {test.id() for test in all_tests}
        core_ids = {test.id() for test in core_tests}
        browser_ids = {test.id() for test in browser_tests}
        self.assertEqual(browser_ids, set(REAL_BROWSER_TEST_IDS))
        self.assertEqual(len(browser_ids), 7)
        self.assertFalse(core_ids & browser_ids)
        self.assertEqual(core_ids | browser_ids, all_ids)
        self.assertEqual(len(core_tests) + len(browser_tests), len(all_tests))

    def test_invalid_shard_count_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            shard_index_for_test_id("test_example.ExampleTests.test_case", 0)

    def test_schema_workflow_preserves_full_validation_gate_around_core_and_browser_suites(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\n  primary:\n", workflow)
        self.assertIn("name: preflight + core tests (2/2)", workflow)
        self.assertIn("\n  parallel:\n", workflow)
        self.assertIn("name: core tests (1/2)", workflow)
        self.assertIn("\n  real_browser:\n", workflow)
        self.assertIn("name: real-browser acceptance", workflow)
        self.assertIn("\n  validate:\n", workflow)
        self.assertIn(
            "scripts/run_unittest_shard.py --suite core --shard-count 2 --verify-only",
            workflow,
        )
        self.assertIn("--suite core", workflow)
        self.assertIn("--shard-index 1", workflow)
        self.assertIn("--shard-index 0", workflow)
        self.assertIn("--suite real-browser", workflow)
        self.assertIn("--shard-count 1", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("- primary", workflow)
        self.assertIn("- parallel", workflow)
        self.assertIn("- real_browser", workflow)
        self.assertIn("PRIMARY_RESULT: ${{ needs.primary.result }}", workflow)
        self.assertIn("PARALLEL_RESULT: ${{ needs.parallel.result }}", workflow)
        self.assertIn("BROWSER_RESULT: ${{ needs.real_browser.result }}", workflow)
        self.assertNotIn("needs: preflight", workflow)
        self.assertNotIn("python -m unittest discover -s tests -v", workflow)


if __name__ == "__main__":
    unittest.main()
