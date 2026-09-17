import json
from pathlib import Path
import tempfile
import unittest

from scripts.adopt_publication_sources import plan
from scripts.render_candidate_source_lock import main as render_candidate_main
from scripts.reconcile_publication import reconcile
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

    def test_candidate_renderer_requires_explicit_modeling_and_preserves_current_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(self._lock())
            import sys
            original = sys.argv
            try:
                sys.argv = [
                    "render_candidate_source_lock.py",
                    "--lock", str(current),
                    "--output", str(candidate),
                    "--candidate-provider", "modeling",
                    "--override", "modeling=" + "d" * 40,
                ]
                self.assertEqual(render_candidate_main(), 0)
            finally:
                sys.argv = original
            value = json.loads(candidate.read_text())
            self.assertEqual(value["schema_version"], 2)
            self.assertEqual(set(value["publications"]), {"modeling", "composition", "policy"})
            self.assertEqual(json.loads(current.read_text())["schema_version"], 1)

    def test_reconciliation_is_shadow_by_default_and_requires_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            report = root / "report.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report.write_text(json.dumps({
                "schema_version": 1,
                "classification": "NOT_ELIGIBLE",
                "inputs": {
                    "integration_revision": "e" * 40,
                    "modeling_revision": "d" * 40,
                    "composition_revision": "b" * 40,
                    "policy_revision": "c" * 40,
                },
                "trusted": {"policy_revision": "c" * 40, "controller_revision": "e" * 40},
                "checks": {"required": ["producer"], "results": {"producer": "passed"}},
                "evidence_refs": ["workflow://test"],
            }))
            result = reconcile(mode="shadow", current=current, candidate=candidate, qualification=report, authorization=True, kill_switch=False)
            self.assertEqual(result["classification"], "NOT_ELIGIBLE")
            self.assertIn("SHADOW_MODE", result["reason_codes"])

    def test_reconciliation_rejects_report_for_a_different_candidate_tuple(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            report = root / "report.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report.write_text(json.dumps({
                "schema_version": 1,
                "classification": "NOT_ELIGIBLE",
                "inputs": {
                    "integration_revision": "e" * 40,
                    "modeling_revision": "a" * 40,
                    "composition_revision": "b" * 40,
                    "policy_revision": "c" * 40,
                },
                "trusted": {"policy_revision": "c" * 40, "controller_revision": "e" * 40},
                "checks": {"required": ["producer"], "results": {"producer": "passed"}},
                "evidence_refs": ["workflow://test"],
            }))
            result = reconcile(mode="adoption-only", current=current, candidate=candidate,
                               qualification=report, authorization=True, kill_switch=False)
            self.assertEqual(result["classification"], "INVALID_INPUT")
            self.assertIn("QUALIFICATION_INPUT_DOES_NOT_MATCH_CANDIDATE_LOCK", result["reason_codes"])

    def test_reconciliation_separates_shadow_from_explicit_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            report = root / "report.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report.write_text(json.dumps({
                "schema_version": 1,
                "classification": "NOT_ELIGIBLE",
                "inputs": {
                    "integration_revision": "e" * 40,
                    "modeling_revision": "d" * 40,
                    "composition_revision": "b" * 40,
                    "policy_revision": "c" * 40,
                },
                "trusted": {"policy_revision": "c" * 40, "controller_revision": "e" * 40},
                "checks": {"required": ["producer"], "results": {"producer": "passed"}},
                "evidence_refs": ["workflow://test"],
            }))
            result = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, authorization=True, kill_switch=False,
                expected_integration_revision="e" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(result["classification"], "AUTO_PROCESSABLE")
            self.assertEqual(
                set(result["allowed_mutations"]),
                {"publication-sources.json:publications.modeling.revision", "publication-sources.json:schema_version"},
            )

            stopped = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, authorization=True, kill_switch=True,
                expected_integration_revision="e" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(stopped["classification"], "NOT_ELIGIBLE")
            self.assertIn("KILL_SWITCH_ACTIVE", stopped["reason_codes"])


if __name__ == "__main__":
    unittest.main()
