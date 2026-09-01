from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PORTAL_HOME = ROOT / "docs" / "landing.md"
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
    def test_portal_cover_preserves_task_entry_points_and_secondary_architecture_routes(self) -> None:
        portal = PORTAL_HOME.read_text(encoding="utf-8")

        for destination in (
            "web/",
            "website/",
            "webapp/",
            "composition/use/skill-first-use-walkthrough/",
            "skill/",
            "policy/getting-started/",
            "composition/",
            "composition/concepts/",
            "capabilities/",
            "policy/",
        ):
            with self.subTest(destination=destination):
                self.assertIn(f'href="{destination}"', portal)
        self.assertNotIn('href="overview/"', portal)

        self.assertIn(
            'class="portal-artifact-card portal-artifact-card--skill"',
            portal,
        )
        self.assertIn(
            'class="portal-artifact-card portal-artifact-card--webapp"',
            portal,
        )
        self.assertNotIn("portal-artifact-card--policy", portal)
        self.assertIn('class="portal-policy-panel"', portal)
        self.assertIn("Independent task · Policy", portal)

        self.assertIn(
            "You normally do <strong>not</strong> turn this <code>templates</code> repository into your product repository.",
            portal,
        )
        self.assertIn(
            "Policy is a separate authority, not a Composition capability.",
            portal,
        )
        self.assertIn(
            "The Site selects reviewed Composition and Policy revisions by full commit SHA.",
            portal,
        )

    def test_publication_policy_declares_current_entry_points(self) -> None:
        policy = PUBLISHING_POLICY.read_text(encoding="utf-8")
        for entry in (
            "`/composition/`",
            "`/skill/`",
            "`/web/`",
            "`/website/`",
            "`/webapp/`",
            "`/capabilities/`",
            "`/lifecycle/`",
            "`/policy/`",
            "`/repository-trees/`",
            "`/files/`",
            "`/guided/`",
            "`/glossary/`",
        ):
            with self.subTest(entry=entry):
                self.assertIn(entry, policy)
        self.assertNotIn("`/overview/`", policy)
        self.assertIn("Composition and Policy", policy)
        self.assertIn("former Skill/Webapp copyable-template trees are retired", policy)

    def test_integrated_navigation_projects_shared_web_and_sibling_browser_artifacts(self) -> None:
        manifest = json.loads(SITE_MANIFEST.read_text(encoding="utf-8"))
        pages = list(iter_pages(manifest["navigation"]))
        indexed = {
            (page["publication"], page["document"]): page["destination"]
            for page in pages
        }

        self.assertEqual(indexed[("site", "portal-home")], "index.md")
        self.assertNotIn(("site", "portal-overview"), indexed)
        self.assertEqual(indexed[("composition", "overview")], "composition/index.md")
        self.assertEqual(
            indexed[("composition", "composition-concepts")],
            "composition/concepts/index.md",
        )
        self.assertEqual(
            indexed[("composition", "consumer-guide")],
            "composition/use/index.md",
        )
        self.assertEqual(
            indexed[("composition", "release-guide")],
            "composition/release/index.md",
        )
        self.assertEqual(
            indexed[("composition", "composer-reference")],
            "composition/reference/composer.md",
        )
        self.assertEqual(
            indexed[("composition", "skill-overview")],
            "skill/index.md",
        )
        self.assertEqual(
            indexed[("composition", "website-webapp-selection")],
            "web/index.md",
        )
        self.assertEqual(
            indexed[("composition", "website-product-walkthrough")],
            "website/index.md",
        )
        self.assertEqual(
            indexed[("composition", "webapp-product-walkthrough")],
            "webapp/product-walkthrough.md",
        )
        self.assertEqual(
            indexed[("composition", "webapp-overview")],
            "webapp/index.md",
        )
        self.assertEqual(
            indexed[("composition", "web-routes-v1-migration")],
            "web/migrations/routes-v1-to-v2.md",
        )
        self.assertEqual(
            indexed[("composition", "web-routes-v2-migration")],
            "web/migrations/routes-v2-to-v3.md",
        )
        self.assertEqual(
            indexed[("composition", "web-routes-v3-migration")],
            "web/migrations/routes-v3-to-v4.md",
        )
        self.assertEqual(
            indexed[("composition", "surfaces-v2-migration")],
            "webapp/docs/migrations/surfaces-v1-to-v2.md",
        )
        self.assertEqual(
            indexed[("composition", "pwa-offline-v2-migration")],
            "capabilities/pwa/migrations/offline-v1-to-v2.md",
        )
        self.assertEqual(
            indexed[("composition", "pwa-update-v2-migration")],
            "capabilities/pwa/migrations/update-v1-to-v2.md",
        )
        self.assertEqual(
            indexed[("composition", "mcp-apps-interface")],
            "capabilities/mcp-apps/index.md",
        )
        self.assertEqual(
            indexed[("composition", "contract-evolution")],
            "lifecycle/contract-evolution/index.md",
        )
        self.assertEqual(
            indexed[("composition", "release-execution")],
            "lifecycle/release-execution/index.md",
        )
        self.assertEqual(indexed[("policy", "overview")], "policy/index.md")
        self.assertEqual(
            indexed[("policy", "provider-navigation")],
            "policy/provider/index.md",
        )

        publications = {page["publication"] for page in pages}
        self.assertEqual(publications, {"site", "composition", "policy"})
        self.assertNotIn("skill", publications)
        self.assertNotIn("website", publications)
        self.assertNotIn("webapp", publications)

        composition_group = next(
            node for node in manifest["navigation"] if node["title"] == "Composition"
        )
        self.assertEqual(
            [child["title"] for child in composition_group["children"][:7]],
            [
                "Overview",
                "Concepts and terminology",
                "Evaluate Composition",
                "Use Composition",
                "Produce a product release",
                "Composer reference",
                "Documentation index",
            ],
        )

        top_level_titles = [node["title"] for node in manifest["navigation"]]
        self.assertNotIn("Portal overview", top_level_titles)
        self.assertNotIn("Application capabilities", top_level_titles)
        for title in (
            "Composition",
            "Agent Skill",
            "Web",
            "Website",
            "Web application",
            "Reusable capabilities",
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
