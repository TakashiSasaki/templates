import unittest

from scripts.acquire_trusted_integration_receipt import ReceiptError, _validate_report


class TrustedIntegrationReceiptTests(unittest.TestCase):
    def report(self):
        bundle_identity = "a" * 64
        bundle_digest = "b" * 64
        workflow_name = "Notify Site after Integration adoption"
        return {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "classification": "NOT_ELIGIBLE",
            "reason_codes": ["QUALIFICATION_PASSED", "TRUSTED_BUNDLE_EQUIVALENT", "AUTHORIZATION_NOT_GRANTED"],
            "affected_authorities": [],
            "inputs": {
                "integration_revision": "c" * 40,
                "bundle_identity": bundle_identity,
                "bundle_content_digest": bundle_digest,
            },
            "trusted": {"policy_revision": "d" * 40, "controller_revision": "e" * 40},
            "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
            "checks": {"required": [], "results": {}, "not_run": []},
            "evidence_refs": [
                f"workflow://{workflow_name}#3/1",
                f"bundle://{bundle_identity}",
                f"trusted-bundle-equivalence://{bundle_identity}",
            ],
            "allowed_mutations": [],
            "next_action": "verify activation",
            "idempotency_key": "f" * 64,
            "verification": {
                "schema_version": 1,
                "verifier_revision": "e" * 40,
                "source_report_digest": "1" * 64,
                "workflow_run_id": 3,
                "workflow_attempt": 1,
                "workflow_head": "2" * 40,
                "workflow_name": workflow_name,
                "workflow_event": "pull_request",
                "workflow_path": ".github/workflows/integration-promotion-notify.yml",
                "artifact_id": 2,
                "artifact_digest": "sha256:" + "3" * 64,
                "artifact_name": f"publication-bundle-{bundle_identity}-1-promoted",
                "bundle_identity": bundle_identity,
                "bundle_content_digest": bundle_digest,
                "trusted_checks": {
                    "report-shape": "passed",
                    "bundle-contract": "passed",
                    "bundle-equivalence": "passed",
                    "provider-declarations": "passed",
                    "identity-binding": "passed",
                },
            },
        }

    def kwargs(self):
        identity = "a" * 64
        return {
            "receipt_artifact_id": 1,
            "receipt_artifact_digest": "sha256:" + "4" * 64,
            "receipt_artifact_name": f"publication-verification-{identity}-1-promoted",
            "bundle_artifact_id": 2,
            "bundle_artifact_digest": "sha256:" + "3" * 64,
            "bundle_artifact_name": f"publication-bundle-{identity}-1-promoted",
            "run_id": 3,
            "attempt": 1,
            "workflow_head": "2" * 40,
            "workflow_name": "Notify Site after Integration adoption",
            "workflow_event": "pull_request",
            "bundle_identity": identity,
            "bundle_content_digest": "b" * 64,
            "integration_revision": "c" * 40,
            "expected_policy_revision": None,
            "expected_controller_revision": "e" * 40,
        }

    def test_exact_receipt_is_accepted(self):
        _validate_report(self.report(), **self.kwargs())

    def test_bundle_artifact_substitution_is_rejected(self):
        report = self.report()
        report["verification"]["artifact_id"] = 99
        with self.assertRaises(ReceiptError):
            _validate_report(report, **self.kwargs())


if __name__ == "__main__":
    unittest.main()
