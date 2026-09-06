from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReferenceConsumerLandingTests(unittest.TestCase):
    def test_landing_exposes_repository_self_hosting_example(self) -> None:
        landing = (ROOT / "docs" / "landing.md").read_text(encoding="utf-8")
        self.assertIn('id="portal-reference-consumer-title"', landing)
        self.assertIn("Concrete example · Self-hosting", landing)
        self.assertIn(
            'href="coexistence/#self-hosting-reference-consumer"',
            landing,
        )
        self.assertIn("This repository as a reference consumer", landing)

    def test_japanese_landing_exposes_same_example(self) -> None:
        landing = (
            ROOT / "translations" / "ja" / "docs" / "landing.md"
        ).read_text(encoding="utf-8")
        self.assertIn('id="portal-reference-consumer-title"', landing)
        self.assertIn("具体例 · Self-hosting", landing)
        self.assertIn(
            'href="/coexistence/#self-hosting-reference-consumer"',
            landing,
        )

    def test_target_page_describes_real_independent_consumer_state(self) -> None:
        coexistence = (
            ROOT / "docs" / "policy-composition-coexistence.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## Self-hosting reference consumer", coexistence)
        self.assertIn("<!-- reference-consumer:start -->", coexistence)
        for token in (
            "reference-consumer.json",
            ".template-composition/lock.json",
            ".agent-policy.yml",
            ".agent-policy.lock",
            "policy/project.md",
            ".agents/skills/",
            "AGENTS.md",
        ):
            self.assertIn(token, coexistence)


if __name__ == "__main__":
    unittest.main()
