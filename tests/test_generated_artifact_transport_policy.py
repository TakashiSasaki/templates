from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "skills/orchestrate-repository-change/references/generated-artifact-transport.md"


class GeneratedArtifactTransportPolicyTests(unittest.TestCase):
    def test_policy_classifies_payloads_before_transport(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        for required in (
            "Git-tracked authority source",
            "Generated build product",
            "External artifact",
            "expected or observed byte size",
            "text versus binary encoding requirements",
            "whole-file replacement",
            "deterministic provider-owned generator/materializer",
        ):
            self.assertIn(required, text)

    def test_transport_constraints_do_not_redefine_authority(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn("Do not solve a transport problem by changing the authority model", text)
        self.assertIn("do not make a generated projection canonical source", text)
        self.assertIn("do not add a generated build product to Git solely to move it", text)
        self.assertIn("huge inline base64 payloads", text)
        self.assertIn("prefer a mutation mechanism designed for binary/blob transport", text)

    def test_failure_path_is_fail_closed(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn("stop that mutation path", text)
        self.assertIn("Do not silently substitute", text)
        self.assertIn("validate the materialized product at the exact resulting revision", text)

    def test_policy_is_provider_neutral(self) -> None:
        text = POLICY.read_text(encoding="utf-8").lower()
        self.assertNotIn("webmcp", text)


if __name__ == "__main__":
    unittest.main()
