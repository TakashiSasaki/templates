from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.qualify_site_candidate import (
    _candidate_lock_needs_commit,
    _compatibility_check_states,
    _report,
    qualify,
)
from tests.bundle_consumer_fixture import fixture, finish


ROOT = Path(__file__).resolve().parents[1]


class SiteCandidateQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = {
            "schema_version": 1,
            "repository": "TakashiSasaki/templates",
            "revision": "a" * 40,
            "bundle_schema": 4,
            "bundle_identity": "b" * 64,
            "content_digest": "c" * 64,
        }
        self.trusted = {"policy_revision": "d" * 40, "controller_revision": "e" * 40}
        self.checks = {"bundle-integrity": "passed"}

    def test_replay_key_excludes_ephemeral_candidate_commit(self) -> None:
        first = _report(
            self.lock,
            trusted=self.trusted,
            classification="NOT_ELIGIBLE",
            reasons=["AUTHORIZATION_NOT_GRANTED"],
            checks=self.checks,
            evidence=["workflow://run/1"],
            site_revision="f" * 40,
            site_base_revision="1" * 40,
        )
        second = _report(
            self.lock,
            trusted=self.trusted,
            classification="NOT_ELIGIBLE",
            reasons=["AUTHORIZATION_NOT_GRANTED"],
            checks=self.checks,
            evidence=["workflow://run/2"],
            site_revision="0" * 40,
            site_base_revision="1" * 40,
        )
        self.assertNotEqual(first["inputs"]["site_revision"], second["inputs"]["site_revision"])
        self.assertEqual(first["inputs"]["site_base_revision"], second["inputs"]["site_base_revision"])
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_unchanged_lock_is_a_no_change_without_synthetic_commit(self) -> None:
        from pathlib import Path
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "integration-source.json"
            candidate = root / "candidate.json"
            lock = {
                "schema_version": 1,
                "repository": "TakashiSasaki/templates",
                "revision": "a" * 40,
                "bundle_schema": 4,
                "bundle_identity": "b" * 64,
                "content_digest": "c" * 64,
            }
            current.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            candidate.write_text(json.dumps(lock, separators=(",", ":")), encoding="utf-8")
            self.assertFalse(_candidate_lock_needs_commit(root, candidate))
            candidate.write_text(json.dumps({**lock, "revision": "d" * 40}), encoding="utf-8")
            self.assertTrue(_candidate_lock_needs_commit(root, candidate))

    def test_no_change_report_has_no_adoption_action(self) -> None:
        result = _report(
            self.lock,
            trusted=self.trusted,
            classification="NO_CHANGE",
            reasons=["ALREADY_SELECTED"],
            checks=self.checks,
            evidence=[],
            site_revision="f" * 40,
            site_base_revision="1" * 40,
        )
        self.assertEqual(result["next_action"], "no Site lock mutation is required")
        self.assertEqual(result["affected_authorities"], [])

    def test_failed_and_not_run_checks_are_reported_truthfully(self) -> None:
        result = _report(
            self.lock,
            trusted=self.trusted,
            classification="QUALIFICATION_FAILED",
            reasons=["SITE_ARTIFACT_PROVENANCE_FAILED"],
            checks={
                "bundle-integrity": "passed",
                "generic-markdown-renderer": "passed",
                "pages-artifact-provenance": "failed",
            },
            evidence=["test://qualification"],
        )
        self.assertEqual(result["checks"]["results"]["pages-artifact-provenance"], "failed")
        self.assertNotIn("pages-artifact-provenance", result["checks"]["not_run"])

        compatibility = {
            "checks": {
                "required": ["bundle-integrity", "generic-markdown-renderer", "pages-artifact-provenance"],
                "results": {"bundle-integrity": "failed"},
                "not_run": ["generic-markdown-renderer", "pages-artifact-provenance"],
            }
        }
        self.assertEqual(
            _compatibility_check_states(compatibility),
            {
                "bundle-integrity": "failed",
                "generic-markdown-renderer": "not-run",
                "pages-artifact-provenance": "not-run",
            },
        )

    def test_renderer_failure_after_compatibility_success_is_qualification_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = fixture(root / "bundle")
            finish(bundle)
            candidate_lock = root / "candidate-lock.json"
            candidate_lock.write_text(json.dumps(self.lock), encoding="utf-8")
            real_run = subprocess.run

            def fail_renderer(command, *args, **kwargs):
                if any("render_publication_bundle.py" in str(value) for value in command):
                    raise subprocess.CalledProcessError(1, command)
                return real_run(command, *args, **kwargs)

            with patch("scripts.qualify_site_candidate.subprocess.run", side_effect=fail_renderer):
                result = qualify(
                    ROOT,
                    bundle,
                    candidate_lock,
                    trusted=self.trusted,
                    evidence=["test://renderer"],
                )
            self.assertEqual(result["classification"], "QUALIFICATION_FAILED")
            self.assertEqual(result["checks"]["results"]["bundle-integrity"], "passed")
            self.assertEqual(result["checks"]["results"]["generic-markdown-renderer"], "failed")
            self.assertIn("pages-artifact-provenance", result["checks"]["not_run"])


if __name__ == "__main__":
    unittest.main()
