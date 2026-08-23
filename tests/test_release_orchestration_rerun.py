from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import test_release_orchestration as orchestration_helpers


class ReleaseOrchestrationRerunTests(unittest.TestCase):
    def test_same_candidate_rerun_reexecutes_evidence_and_rebuilds_bundle(self) -> None:
        helper = orchestration_helpers.ReleaseOrchestrationTests(
            methodName="test_success_produces_evidence_and_bundle_and_commits_transaction"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, _, _ = helper.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            first = helper.run_release(target, revision)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            evidence_path = target / "contracts/release-evidence.json"
            bundle_path = target / "contracts/release-bundle.json"
            first_evidence = evidence_path.read_bytes()
            first_bundle = bundle_path.read_bytes()

            second = helper.run_release(target, revision)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("Release evidence and bundle produced", second.stdout)
            second_evidence = evidence_path.read_bytes()
            second_bundle = bundle_path.read_bytes()
            self.assertNotEqual(second_evidence, first_evidence)
            self.assertNotEqual(second_bundle, first_bundle)

            evidence = json.loads(second_evidence.decode("utf-8"))
            bundle = json.loads(second_bundle.decode("utf-8"))
            self.assertEqual(evidence["subject"]["revision"], revision)
            self.assertEqual(bundle["subject"]["revision"], revision)
            helper.assert_transaction_state_absent(target)


if __name__ == "__main__":
    unittest.main()
