from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "docs" / "landing.md"
LANDING_JA = ROOT / "translations" / "ja" / "docs" / "landing.md"
MANIFEST = ROOT / "site-manifest.json"
NAV_LOCALES = ROOT / "reader-navigation-locales.json"


class HumanFirstOnboardingTests(unittest.TestCase):
    def test_home_routes_primary_tasks_before_architecture(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        task_section = landing.index("What do you want to do?")
        explore_section = landing.index("Already started, or want the model?")
        self.assertLess(task_section, explore_section)
        for label in (
            "Choose Website or Web application",
            "Create an Agent Skill",
            "Add coding-agent rules to a repository",
        ):
            with self.subTest(label=label):
                self.assertIn(label, landing[:explore_section])

    def test_browser_task_routes_through_canonical_selector(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn('href="web/"', landing)
        self.assertNotIn(
            'href="composition/use/webapp-product-walkthrough/"',
            landing,
        )

    def test_skill_task_links_directly_to_canonical_walkthrough(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn(
            'href="composition/use/skill-first-use-walkthrough/"',
            landing,
        )

    def test_composition_concepts_is_secondary_not_primary_onboarding(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        explore_section = landing.index("Already started, or want the model?")
        concepts = landing.index('href="composition/concepts/"')
        self.assertGreater(concepts, explore_section)
        self.assertNotIn("Composition concepts", landing[:explore_section])


    def test_separate_product_repository_mental_model_is_explicit(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn("Use the systems supplied by this repository in another repository.", landing)
        self.assertIn("your separate product repository", landing)
        self.assertIn("provides tooling and contracts", landing)

    def test_policy_is_presented_as_independent_task(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn('href="policy/getting-started/"', landing)
        self.assertIn("Policy is a separate authority, not a Composition capability", landing)

    def test_japanese_landing_preserves_selector_first_task_routes(self) -> None:
        landing = LANDING_JA.read_text(encoding="utf-8")
        for href in (
            "/web/",
            "/composition/use/skill-first-use-walkthrough/",
            "/policy/getting-started/",
        ):
            with self.subTest(href=href):
                self.assertIn(f'href="{href}"', landing)
        self.assertNotIn("/composition/use/webapp-product-walkthrough/", landing)
        self.assertIn("あなたの別 product repository", landing)
        explore_section = landing.index("すでに始めている、または仕組みを知りたい")
        concepts = landing.index('href="/composition/concepts/"')
        self.assertGreater(concepts, explore_section)



if __name__ == "__main__":
    unittest.main()
