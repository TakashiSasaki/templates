import json
import hashlib
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

    def _qualification(self, root, inputs):
        """Build a synthetic receipt; candidate claims alone are not enough."""
        source = root / "source-report.json"
        source.write_bytes(b"candidate report bytes")
        bundle_identity = "a" * 64
        content_digest = "b" * 64
        report = {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "classification": "NOT_ELIGIBLE",
            "reason_codes": ["AUTHORIZATION_NOT_GRANTED"],
            "affected_authorities": [],
            "inputs": {
                **inputs,
                "bundle_identity": bundle_identity,
                "bundle_content_digest": content_digest,
            },
            "trusted": {"policy_revision": "c" * 40, "controller_revision": "e" * 40},
            "checks": {"required": ["producer"], "results": {"producer": "passed"}},
            "evidence_refs": ["workflow://test"],
            "verification": {
                "schema_version": 1,
                "verifier_revision": "e" * 40,
                "source_report_digest": hashlib.sha256(source.read_bytes()).hexdigest(),
                "workflow_run_id": 1,
                "workflow_attempt": 1,
                "workflow_head": "e" * 40,
                "workflow_name": "test-workflow",
                "workflow_event": "workflow_dispatch",
                "workflow_path": ".github/workflows/integration-reconcile.yml",
                "artifact_id": 2,
                "artifact_digest": "sha256:" + "d" * 64,
                "artifact_name": "publication-bundle-" + bundle_identity + "-1-test",
                "bundle_identity": bundle_identity,
                "bundle_content_digest": content_digest,
                "trusted_checks": {
                    "report-shape": "passed",
                    "bundle-contract": "passed",
                    "bundle-equivalence": "passed",
                    "provider-declarations": "passed",
                    "identity-binding": "passed",
                },
            },
        }
        receipt = root / "verified-report.json"
        receipt.write_text(json.dumps(report), encoding="utf-8")
        return receipt, source

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
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report, source = self._qualification(root, {
                    "integration_revision": "e" * 40,
                    "modeling_revision": "d" * 40,
                    "composition_revision": "b" * 40,
                    "policy_revision": "c" * 40,
            })
            result = reconcile(mode="shadow", current=current, candidate=candidate, qualification=report, source_qualification=source, authorization=True, kill_switch=False)
            self.assertEqual(result["classification"], "NOT_ELIGIBLE")
            self.assertIn("SHADOW_MODE", result["reason_codes"])

    def test_reconciliation_rejects_report_for_a_different_candidate_tuple(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report, source = self._qualification(root, {
                    "integration_revision": "e" * 40,
                    "modeling_revision": "a" * 40,
                    "composition_revision": "b" * 40,
                    "policy_revision": "c" * 40,
            })
            result = reconcile(mode="adoption-only", current=current, candidate=candidate,
                               qualification=report, source_qualification=source, authorization=True, kill_switch=False)
            self.assertEqual(result["classification"], "INVALID_INPUT")
            self.assertIn("QUALIFICATION_INPUT_DOES_NOT_MATCH_CANDIDATE_LOCK", result["reason_codes"])

    def test_reconciliation_separates_shadow_from_explicit_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report, source = self._qualification(root, {
                    "integration_revision": "e" * 40,
                    "modeling_revision": "d" * 40,
                    "composition_revision": "b" * 40,
                    "policy_revision": "c" * 40,
            })
            result = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, source_qualification=source, authorization=True, kill_switch=False,
                expected_integration_revision="e" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(result["classification"], "AUTO_PROCESSABLE")
            self.assertEqual(
                set(result["allowed_mutations"]),
                {
                    "publication-sources.json:publications.modeling.revision",
                    "publication-sources.json:schema_version",
                    "publication-promotion-intent.json",
                },
            )

            stopped = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, source_qualification=source, authorization=True, kill_switch=True,
                expected_integration_revision="e" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(stopped["classification"], "NOT_ELIGIBLE")
            self.assertIn("KILL_SWITCH_ACTIVE", stopped["reason_codes"])

    def test_already_selected_tuple_requires_and_produces_a_reviewable_promotion_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            selected = self._lock(modeling="d" * 40)
            current.write_bytes(selected)
            candidate.write_bytes(selected)
            report, source = self._qualification(root, {
                "integration_revision": "e" * 40,
                "modeling_revision": "d" * 40,
                "composition_revision": "b" * 40,
                "policy_revision": "c" * 40,
            })

            authorized = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, source_qualification=source, authorization=True, kill_switch=False,
                expected_integration_revision="e" * 40,
                expected_consumer_base="e" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(authorized["classification"], "AUTO_PROCESSABLE")
            self.assertEqual(authorized["reason_codes"][-1], "SELECTION_ALREADY_CURRENT")
            self.assertEqual(authorized["allowed_mutations"], ["publication-promotion-intent.json"])

            unauthorized = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, source_qualification=source, authorization=False, kill_switch=False,
                expected_integration_revision="e" * 40,
                expected_consumer_base="e" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(unauthorized["classification"], "NOT_ELIGIBLE")
            self.assertIn("AUTHORIZATION_NOT_GRANTED", unauthorized["reason_codes"])

    def test_reconciliation_stops_when_consumer_base_is_not_the_qualified_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            candidate = root / "candidate.json"
            current.write_bytes(self._lock())
            candidate.write_bytes(self._lock(modeling="d" * 40))
            report, source = self._qualification(root, {
                "integration_revision": "e" * 40,
                "modeling_revision": "d" * 40,
                "composition_revision": "b" * 40,
                "policy_revision": "c" * 40,
            })
            result = reconcile(
                mode="adoption-only", current=current, candidate=candidate,
                qualification=report, source_qualification=source, authorization=True, kill_switch=False,
                expected_integration_revision="e" * 40,
                expected_consumer_base="f" * 40,
                expected_policy_revision="c" * 40,
                expected_controller_revision="e" * 40,
            )
            self.assertEqual(result["classification"], "SUPERSEDED")
            self.assertIn("CONSUMER_BASE_DOES_NOT_MATCH_PRODUCER", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
