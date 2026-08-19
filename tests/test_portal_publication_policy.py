from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PORTAL_HOME = ROOT / "docs/landing.md"
PORTAL_OVERVIEW = ROOT / "docs/overview.md"
README = ROOT / "README.md"
PUBLISHING_POLICY = ROOT / "PUBLISHING.md"
SITE_MANIFEST = ROOT / "site-manifest.json"
SOURCE_LOCK = ROOT / "publication-sources.json"


def iter_pages(nodes: list[dict[str, Any]]):
    for node in nodes:
        if "children" in node:
            yield from iter_pages(node["children"])
        else:
            yield node


class PortalPublicationPolicyTests(unittest.TestCase):
    def test_portal_cover_preserves_artifact_entry_points_and_exposes_composition(self) -> None:
        portal = PORTAL_HOME.read_text(encoding="utf-8")

        for destination in (
            "overview/",
            "composition/",
            "capabilities/",
            "skill/",
            "policy/",
            "webapp/",
        ):
            with self.subTest(destination=destination):
                self.assertIn(f'href="{destination}"', portal)
        for label in ("Agent Skill", "Policy", "Web application"):
            with self.subTest(label=label):
                self.assertIn(
                    f'class="portal-domain-card__label">{label}</span>',
                    portal,
                )
        self.assertIn("One reviewed Composition authority", portal)
        self.assertIn("The Site locks both providers by full commit SHA", portal)

    def test_portal_overview_explains_two_provider_model(self) -> None:
        overview = PORTAL_OVERVIEW.read_text(encoding="utf-8")

        self.assertIn("explicit allowlists", overview)
        self.assertIn("full 40-character commit SHAs", overview)
        self.assertIn("build-provenance.json", overview)
        self.assertIn("Machine-readable contracts and schemas", overview)
        self.assertIn(
            "external provider set is now <code>composition</code> and <code>policy</code>",
            overview,
        )
        self.assertIn("Composition does not merge artifact semantics", overview)

    def test_publication_policy_declares_current_entry_points(self) -> None:
        policy = PUBLISHING_POLICY.read_text(encoding="utf-8")
        for entry in (
            "`/composition/`",
            "`/skill/`",
            "`/capabilities/`",
            "`/webapp/`",
            "`/lifecycle/`",
            "`/policy/`",
            "`/repository-trees/`",
            "`/files/`",
            "`/guided/`",
            "`/glossary/`",
        ):
            with self.subTest(entry=entry):
                self.assertIn(entry, policy)
        self.assertIn("Composition and Policy", policy)
        self.assertIn("former Skill/Webapp copyable-template trees are retired", policy)

    def test_integrated_navigation_uses_composition_as_skill_and_webapp_authority(self) -> None:
        manifest = json.loads(SITE_MANIFEST.read_text(encoding="utf-8"))
        pages = list(iter_pages(manifest["navigation"]))
        indexed = {
            (page["publication"], page["document"]): page["destination"]
            for page in pages
        }

        self.assertEqual(indexed[("site", "portal-home")], "index.md")
        self.assertEqual(
            indexed[("site", "portal-overview")],
            "overview/index.md",
        )
        self.assertEqual(
            indexed[("composition", "overview")],
            "composition/index.md",
        )
        self.assertEqual(
            indexed[("composition", "skill-overview")],
            "skill/index.md",
        )
        self.assertEqual(
            indexed[("composition", "mcp-apps-interface")],
            "capabilities/mcp-apps/index.md",
        )
        self.assertEqual(
            indexed[("composition", "webapp-overview")],
            "webapp/index.md",
        )
        self.assertEqual(
            indexed[("composition", "contract-evolution")],
            "lifecycle/contract-evolution/index.md",
        )
        self.assertEqual(indexed[("policy", "overview")], "policy/index.md")
        self.assertEqual(
            indexed[("policy", "provider-navigation")],
            "policy/provider/index.md",
        )

        publications = {page["publication"] for page in pages}
        self.assertEqual(publications, {"site", "composition", "policy"})
        self.assertNotIn("skill", publications)
        self.assertNotIn("webapp", publications)

        top_level_titles = [node["title"] for node in manifest["navigation"]]
        for title in (
            "Portal overview",
            "Composition",
            "Agent Skill",
            "Application capabilities",
            "Web application",
            "Lifecycle contracts",
            "Policy",
        ):
            self.assertIn(title, top_level_titles)

    def test_provider_inputs_are_locked_to_full_commit_shas(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(
            set(lock["publications"]),
            {"composition", "policy"},
        )
        for publication, entry in lock["publications"].items():
            with self.subTest(publication=publication):
                self.assertRegex(entry["revision"], re.compile(r"^[0-9a-f]{40}$"))

    def test_normative_policy_rejects_implicit_and_branch_wide_publication(self) -> None:
        policy = PUBLISHING_POLICY.read_text(encoding="utf-8")

        self.assertIn("Publication catalogs are explicit allowlists", policy)
        self.assertIn("Branch-wide copies", policy)
        self.assertIn("unrestricted glob-based publication", policy)
        self.assertIn("Adding a file to a provider branch does not publish it", policy)
        self.assertIn("Generated destinations are stable public paths", policy)

    def test_deployment_environment_remains_external_release_gate(self) -> None:
        policy = " ".join(PUBLISHING_POLICY.read_text(encoding="utf-8").split())
        readme = " ".join(README.read_text(encoding="utf-8").split())

        self.assertIn(
            "custom deployment branch policy must allow exactly the `site` branch",
            policy,
        )
        self.assertIn("obsolete `main` authorization has been removed", policy)
        self.assertIn("Do not broaden the environment to all branches", policy)
        self.assertIn("Pull requests cannot change this setting", readme)
        self.assertIn(
            "`https://templates.moukaeritai.work/` is the configured Pages base URL",
            policy,
        )
        self.assertIn("HTTPS enforcement is enabled", policy)
        self.assertIn("https://templates.moukaeritai.work/", readme)


if __name__ == "__main__":
    unittest.main()
