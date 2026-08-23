from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_release_orchestration as orchestration_helpers


class ReleaseOrchestrationBoundaryTests(unittest.TestCase):
    def helper(self) -> orchestration_helpers.ReleaseOrchestrationTests:
        return orchestration_helpers.ReleaseOrchestrationTests(
            methodName="test_success_produces_evidence_and_bundle_and_commits_transaction"
        )

    def test_proof_cannot_mutate_downstream_bundle_under_rerun_exclusion(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = helper.materialize(
                Path(temp_dir),
                "from pathlib import Path\n"
                "Path('contracts/release-bundle.json').write_text('proof mutation\\n', encoding='utf-8')\n",
            )
            result = helper.run_release(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(
                "release evidence stage modified downstream release bundle",
                result.stderr,
            )
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            helper.assert_transaction_state_absent(target)

    def test_standalone_evidence_cli_remains_strict_after_bundle_publication(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_helper, target, revision, _, _ = helper.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            released = helper.run_release(target, revision)
            self.assertEqual(released.returncode, 0, released.stdout + released.stderr)

            standalone = evidence_helper.run_producer(target, revision)
            self.assertEqual(standalone.returncode, 2, standalone.stdout + standalone.stderr)
            self.assertIn("raw tracked bytes differ", standalone.stderr)
            self.assertIn("contracts/release-bundle.json", standalone.stderr)


if __name__ == "__main__":
    unittest.main()
