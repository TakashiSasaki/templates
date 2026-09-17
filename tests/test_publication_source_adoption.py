import json
from pathlib import Path
import tempfile
import unittest

from scripts.adopt_publication_sources import plan
from scripts.resolve_publication_sources import render_source_lock


class PublicationSourceAdoptionTests(unittest.TestCase):
    def _lock(self, modeling=None):
        revisions = {"composition": "b" * 40, "policy": "c" * 40}
        if modeling is not None:
            revisions = {"modeling": modeling, **revisions}
        return render_source_lock(revisions)

    def test_modeling_addition_is_an_explicit_schema_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="a" * 40))
            result = plan(current, candidate)
            self.assertEqual(result["classification"], "AUTO_PROCESSABLE")
            self.assertIn("publications.modeling.revision", result["changed_fields"])
            self.assertIn("schema_version", result["changed_fields"])

    def test_unrelated_lock_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(self._lock())
            value = json.loads(current.read_text())
            value["repository"] = "other/repository"
            candidate.write_text(json.dumps(value, indent=2) + chr(10))
            with self.assertRaisesRegex(Exception, "repository"):
                plan(current, candidate)


if __name__ == "__main__":
    unittest.main()
