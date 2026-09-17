"""Negative tests for the trusted qualification/adoption boundary."""
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.verify_bundle_equivalence import BundleEquivalenceError, verify
from tests.test_publication_bundle import finish, fixture


class TrustedQualificationBoundaryTests(unittest.TestCase):
    def test_trusted_equivalence_rejects_candidate_payload_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = fixture(root / "candidate")
            finish(candidate)
            trusted = root / "trusted"
            shutil.copytree(candidate, trusted)
            self.assertEqual(verify(candidate, trusted)["classification"], "TRUSTED_EQUIVALENT")
            (candidate / "publication" / "intro.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(BundleEquivalenceError):
                verify(candidate, trusted)

    def test_trusted_equivalence_rejects_unlisted_candidate_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = fixture(root / "candidate")
            finish(candidate)
            trusted = root / "trusted"
            shutil.copytree(candidate, trusted)
            (candidate / "publication" / "unlisted.txt").write_text("unexpected\n", encoding="utf-8")
            with self.assertRaises(BundleEquivalenceError):
                verify(candidate, trusted)


if __name__ == "__main__":
    unittest.main()
