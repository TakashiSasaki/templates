from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import test_release_bundle_producer as bundle_helpers


class ReleaseBundleProducerRerunTests(unittest.TestCase):
    def helper(self) -> bundle_helpers.ReleaseBundleProducerTests:
        return bundle_helpers.ReleaseBundleProducerTests(
            methodName="test_success_produces_manifest_ordered_digest_closed_bundle"
        )

    def test_same_revision_can_replace_prior_generated_bundle(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, _ = helper.approved_candidate(Path(temp_dir))
            first = helper.run_bundle(target, revision)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            bundle_path = target / "contracts/release-bundle.json"
            first_bytes = bundle_path.read_bytes()
            first_document = json.loads(first_bytes)

            second = helper.run_bundle(target, revision)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            second_bytes = bundle_path.read_bytes()
            second_document = json.loads(second_bytes)
            self.assertNotEqual(second_bytes, first_bytes)
            self.assertEqual(second_document["subject"]["revision"], revision)
            self.assertEqual(second_document["handoff"]["status"], "ready")
            self.assertGreater(
                second_document["provenance"]["generatedAt"],
                first_document["provenance"]["generatedAt"],
            )


if __name__ == "__main__":
    unittest.main()
