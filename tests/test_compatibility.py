from __future__ import annotations

import copy
import unittest

from integration.compatibility import classify_preflight, classify_qualification


SHA = "a" * 40
POLICY = "b" * 40
CONTROLLER = "c" * 40


def payload() -> dict:
    return {
        "boundary": "provider-to-integration",
        "candidate": {
            "providers": {"modeling": SHA, "composition": SHA, "policy": SHA},
            "requirements": [
                {"feature": "publication.generic-document.v1", "required": True, "fallback": "generic-document"}
            ],
            "destinations": ["modeling/index.md"],
        },
        "consumer": {
            "protocol": "publication-bundle",
            "supported_features": ["publication.generic-document.v1"],
        },
        "registry": {"modeling": "TakashiSasaki/templates", "composition": "TakashiSasaki/templates", "policy": "TakashiSasaki/templates"},
        "inputs": {"modeling_revision": SHA, "composition_revision": SHA, "policy_revision": SHA},
        "trusted": {"policy_revision": POLICY, "controller_revision": CONTROLLER},
    }


class CompatibilityTests(unittest.TestCase):
    def test_malformed_envelope_returns_structured_invalid_report(self):
        report = classify_preflight({})
        self.assertEqual(report["classification"], "INVALID_INPUT")
        self.assertIsNone(report["boundary"])
        self.assertEqual(report["next_action"], "stop")

    def test_preflight_never_authorizes(self):
        report = classify_preflight(payload())
        self.assertEqual(report["classification"], "COMPATIBLE_PENDING_QUALIFICATION")

    def test_generic_document_fallback_is_not_adaptation(self):
        value = payload()
        value["consumer"]["supported_features"] = []
        value["candidate"]["requirements"][0]["fallback"] = "generic-document"
        report = classify_preflight(value)
        self.assertEqual(report["classification"], "ADAPTATION_REQUIRED")

    def test_explicit_generic_fallback_is_processable(self):
        value = payload()
        feature = "publication.opaque-json.v1"
        value["candidate"]["requirements"] = [{
            "feature": feature,
            "required": True,
            "fallback": "generic-document",
        }]
        value["consumer"]["supported_features"] = ["publication.generic-document.v1"]
        value["consumer"]["fallbacks"] = {feature: "generic-document"}
        report = classify_preflight(value)
        self.assertEqual(report["classification"], "COMPATIBLE_PENDING_QUALIFICATION")
        self.assertEqual(report["requirements"]["fallbacks"], {feature: "generic-document"})

    def test_unsupported_required_feature_is_adaptation(self):
        value = payload()
        value["candidate"]["requirements"][0]["fallback"] = "none"
        value["consumer"]["supported_features"] = []
        report = classify_preflight(value)
        self.assertEqual(report["classification"], "ADAPTATION_REQUIRED")

    def test_duplicate_destination_is_conflict(self):
        value = payload()
        value["candidate"]["destinations"] = ["same.md", "same.md"]
        self.assertEqual(classify_preflight(value)["classification"], "CROSS_PROVIDER_CONFLICT")

    def test_unknown_protocol_is_not_invalid_schema(self):
        value = payload()
        value["consumer"]["protocol"] = "new-unknown-protocol"
        report = classify_preflight(value)
        self.assertEqual(report["classification"], "UNKNOWN")
        self.assertIn("UNKNOWN_PROTOCOL", report["reason_codes"])

    def test_required_check_missing_is_failed_closed(self):
        value = payload()
        value["checks"] = {"required": ["producer", "renderer"], "results": {"producer": "passed"}}
        value["authorization"] = True
        report = classify_qualification(value)
        self.assertEqual(report["classification"], "QUALIFICATION_FAILED")

    def test_qualification_requires_authorization_after_checks(self):
        value = payload()
        value["checks"] = {"required": ["producer", "renderer"], "results": {"producer": "passed", "renderer": "passed"}}
        report = classify_qualification(value)
        self.assertEqual(report["classification"], "NOT_ELIGIBLE")

    def test_qualification_can_be_processable(self):
        value = payload()
        value["checks"] = {"required": ["producer", "renderer"], "results": {"producer": "passed", "renderer": "passed"}}
        value["authorization"] = True
        value["evidence_refs"] = ["artifact://bundle"]
        report = classify_qualification(value)
        self.assertEqual(report["classification"], "AUTO_PROCESSABLE")
        self.assertEqual(len(report["idempotency_key"]), 64)

    def test_bad_provider_identity_is_invalid(self):
        value = copy.deepcopy(payload())
        value["candidate"]["providers"]["modeling"] = "main"
        self.assertEqual(classify_preflight(value)["classification"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
