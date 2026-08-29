from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"


class PullRequestMergeGateRoutingEvidenceReuseTests(unittest.TestCase):
    def test_composition_routing_uses_selective_evidence_invalidation(self) -> None:
        routing = AGENTS.read_text(encoding="utf-8").lower()

        for invariant in (
            "invalidate evidence bound to the previous head",
            "reacquiring only the evidence whose bindings changed",
            "do not discard unaffected evidence",
            "do not automatically discard unrelated exact-head ci or review evidence",
            "do not become mandatory gates unless current repository authority requires them",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, routing)

        self.assertNotIn("discard final acceptance for the previous head", routing)
        self.assertNotIn("run the merge gate again", routing)


if __name__ == "__main__":
    unittest.main()
