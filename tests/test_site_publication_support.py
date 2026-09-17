import json
from pathlib import Path
import tempfile
import unittest

from publication_bundle.contract import canonical
from scripts.adopt_integration_source import plan


ROOT = Path(__file__).resolve().parents[1]


class SitePublicationSupportTests(unittest.TestCase):
    def _lock(self, **overrides):
        value = {
            "schema_version": 1,
            "repository": "TakashiSasaki/templates",
            "revision": "a" * 40,
            "bundle_schema": 3,
            "bundle_identity": "b" * 64,
            "content_digest": "c" * 64,
        }
        value.update(overrides)
        return value

    def test_site_support_contract_is_versioned_and_generic(self):
        value = json.loads((ROOT / "contracts/site-publication-support.json").read_text())
        self.assertEqual(value["schema_version"], 1)
        self.assertIn("publication.generic-document.v1", value["supported_features"])

    def test_adoption_plan_only_changes_selected_identity_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(canonical(self._lock()))
            candidate.write_bytes(canonical(self._lock(revision="d" * 40, bundle_schema=4, bundle_identity="e" * 64, content_digest="f" * 64)))
            result = plan(current, candidate)
            self.assertEqual(result["classification"], "AUTO_PROCESSABLE")
            self.assertEqual(set(result["changed_fields"]), {"revision", "bundle_schema", "bundle_identity", "content_digest"})

    def test_dry_run_does_not_mutate_the_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(canonical(self._lock()))
            candidate.write_bytes(canonical(self._lock(revision="d" * 40)))
            before = current.read_bytes()
            plan(current, candidate)
            self.assertEqual(current.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
