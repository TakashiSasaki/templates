from __future__ import annotations

import unittest

from scripts.qualify_site_candidate import _candidate_lock_needs_commit, _report


class SiteCandidateQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = {
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


if __name__ == "__main__":
    unittest.main()
