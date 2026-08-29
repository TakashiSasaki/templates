from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "docs" / "landing.md"
LANDING_JA = ROOT / "translations" / "ja" / "docs" / "landing.md"
MANIFEST = ROOT / "site-manifest.json"
SOURCE_LOCK = ROOT / "publication-sources.json"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"
NAV_LOCALES = ROOT / "reader-navigation-locales.json"
COMPOSITION_REVISION = "870237a771561b78a46ebba8e81b9f134d587f58"


class HumanFirstOnboardingTests(unittest.TestCase):
    def test_home_routes_primary_tasks_before_architecture(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        task_section = landing.index("What do you want to do?")
        explore_section = landing.index("Already started, or want the model?")
        self.assertLess(task_section, explore_section)
        for label in (
            "Create a Web application",
            "Create an Agent Skill",
            "Add coding-agent rules to a repository",
        ):
            with self.subTest(label=label):
                self.assertIn(label, landing[:explore_section])

    def test_webapp_task_links_directly_to_canonical_walkthrough(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn(
            'href="composition/use/webapp-product-walkthrough/"',
            landing,
        )
        manifest = MANIFEST.read_text(encoding="utf-8")
        self.assertIn('"document": "webapp-product-walkthrough"', manifest)
        self.assertIn(
            '"destination": "composition/use/webapp-product-walkthrough.md"',
            manifest,
        )

    def test_skill_task_links_directly_to_canonical_walkthrough(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn(
            'href="composition/use/skill-first-use-walkthrough/"',
            landing,
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        agent_skill = next(
            node for node in manifest["navigation"] if node["title"] == "Agent Skill"
        )
        first = agent_skill["children"][0]
        self.assertEqual(first["document"], "skill-first-use-walkthrough")
        self.assertEqual(
            first["destination"],
            "composition/use/skill-first-use-walkthrough.md",
        )

    def test_composition_concepts_is_secondary_not_primary_onboarding(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        explore_section = landing.index("Already started, or want the model?")
        concepts = landing.index('href="composition/concepts/"')
        self.assertGreater(concepts, explore_section)
        self.assertNotIn("Composition concepts", landing[:explore_section])

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        composition = next(
            node for node in manifest["navigation"] if node["title"] == "Composition"
        )
        concepts_entry = next(
            node
            for node in composition["children"]
            if node.get("document") == "composition-concepts"
        )
        self.assertEqual(concepts_entry["title"], "Concepts and terminology")
        self.assertEqual(concepts_entry["destination"], "composition/concepts/index.md")

    def test_site_locks_the_reviewed_human_onboarding_provider_revisions(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(
            lock["publications"]["composition"]["revision"],
            COMPOSITION_REVISION,
        )
        self.assertEqual(
            lock["publications"]["policy"]["revision"],
            "56448995f848ae2de0f38c49ceb1d35f55461ed1",
        )
        deployment = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))
        self.assertEqual(deployment["locked_composition_revision"], COMPOSITION_REVISION)

    def test_separate_product_repository_mental_model_is_explicit(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn("do <strong>not</strong> turn this <code>templates</code> repository", landing)
        self.assertIn("your separate product repository", landing)
        self.assertIn("provides tooling and contracts", landing)

    def test_policy_is_presented_as_independent_task(self) -> None:
        landing = LANDING.read_text(encoding="utf-8")
        self.assertIn('href="policy/getting-started/"', landing)
        self.assertIn("Policy is a separate authority, not a Composition capability", landing)

    def test_japanese_landing_preserves_same_task_routes(self) -> None:
        landing = LANDING_JA.read_text(encoding="utf-8")
        for href in (
            '/composition/use/webapp-product-walkthrough/',
            '/composition/use/skill-first-use-walkthrough/',
            '/policy/getting-started/',
        ):
            with self.subTest(href=href):
                self.assertIn(f'href="{href}"', landing)
        self.assertIn("あなたの別 product repository", landing)
        explore_section = landing.index("すでに始めている、または仕組みを知りたい")
        concepts = landing.index('href="/composition/concepts/"')
        self.assertGreater(concepts, explore_section)

    def test_concepts_navigation_has_japanese_label(self) -> None:
        locales = json.loads(NAV_LOCALES.read_text(encoding="utf-8"))
        ja = next(locale for locale in locales["locales"] if locale["language"] == "ja")
        label = next(
            item for item in ja["labels"] if item["canonical"] == "Concepts and terminology"
        )
        self.assertEqual(label["localized"], "概念と用語")


if __name__ == "__main__":
    unittest.main()
