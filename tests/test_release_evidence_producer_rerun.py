from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import test_release_evidence_producer as producer_helpers


class ReleaseEvidenceProducerRerunTests(unittest.TestCase):
    def helper(self) -> producer_helpers.ReleaseEvidenceProducerTests:
        return producer_helpers.ReleaseEvidenceProducerTests(
            methodName="test_success_produces_revision_bound_valid_evidence"
        )

    def test_same_revision_can_replace_prior_generated_evidence(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, _ = helper.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            first = helper.run_producer(target, revision)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            evidence_path = target / "contracts/release-evidence.json"
            first_bytes = evidence_path.read_bytes()
            first_document = json.loads(first_bytes)

            second = helper.run_producer(target, revision)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            second_bytes = evidence_path.read_bytes()
            second_document = json.loads(second_bytes)
            self.assertNotEqual(second_bytes, first_bytes)
            self.assertEqual(second_document["subject"]["revision"], revision)
            self.assertEqual(second_document["decision"]["status"], "approved")
            self.assertGreater(
                second_document["provenance"]["generatedAt"],
                first_document["provenance"]["generatedAt"],
            )

    def test_proof_cannot_modify_existing_release_evidence(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = helper.materialize_candidate(
                Path(temp_dir),
                "from pathlib import Path\n"
                "Path('contracts/release-evidence.json').write_text('\\n{}\\n', encoding='utf-8')\n",
            )
            result = helper.run_producer(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(
                "release command modified canonical release evidence",
                result.stderr,
            )
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original,
            )


if __name__ == "__main__":
    unittest.main()
