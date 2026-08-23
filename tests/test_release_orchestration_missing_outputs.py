from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_release_orchestration as orchestration_helpers


class ReleaseOrchestrationMissingOutputTests(unittest.TestCase):
    def helper(self) -> orchestration_helpers.ReleaseOrchestrationTests:
        return orchestration_helpers.ReleaseOrchestrationTests(
            methodName="test_recover_only_restores_digest_verified_preoperation_bytes"
        )

    def test_proof_deleting_downstream_bundle_is_rolled_back(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = helper.materialize(
                Path(temp_dir),
                "from pathlib import Path\n"
                "Path('contracts/release-bundle.json').unlink()\n",
            )
            result = helper.run_release(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            helper.assert_transaction_state_absent(target)

    def test_recovery_recreates_missing_canonical_bundle_from_backup(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = helper.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            helper.write_interrupted_transaction(
                target,
                revision,
                original_evidence,
                original_bundle,
            )
            evidence_path = target / "contracts/release-evidence.json"
            bundle_path = target / "contracts/release-bundle.json"
            evidence_path.write_bytes(b"partial evidence\n")
            bundle_path.unlink()

            recovered = helper.run_release(target, recover_only=True)
            self.assertEqual(
                recovered.returncode,
                0,
                recovered.stdout + recovered.stderr,
            )
            self.assertIn("Recovered incomplete release transaction", recovered.stdout)
            self.assertEqual(evidence_path.read_bytes(), original_evidence)
            self.assertEqual(bundle_path.read_bytes(), original_bundle)
            helper.assert_transaction_state_absent(target)


if __name__ == "__main__":
    unittest.main()
