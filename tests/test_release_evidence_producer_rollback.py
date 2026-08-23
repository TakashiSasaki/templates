from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_release_evidence_producer import ReleaseEvidenceProducerTests


class ReleaseEvidenceProducerRollbackTests(unittest.TestCase):
    def helper(self) -> ReleaseEvidenceProducerTests:
        return ReleaseEvidenceProducerTests(
            methodName="test_success_produces_revision_bound_valid_evidence"
        )

    def test_post_write_validation_failure_restores_exact_seed_bytes(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            target, _, original = helper.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            validator_relative = (
                ".template-composition/validators/validate_release_evidence.py"
            )
            (target / validator_relative).write_text(
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            helper.run_git(target, "add", validator_relative)
            helper.run_git(target, "commit", "--quiet", "--amend", "--no-edit")
            revision = helper.run_git(
                target, "rev-parse", "--verify", "HEAD^{commit}"
            )

            result = helper.run_producer(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("produced evidence validation failed", result.stderr)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original,
            )


if __name__ == "__main__":
    unittest.main()
