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


def iter_pages(nodes: list[dict[str, Any]] | dict[str, Any]):
    if isinstance(nodes, dict):
        for child in nodes.values():
            if isinstance(child, list):
                yield from iter_pages(child)
        return
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
            "Use the systems supplied by this repository in another repository.",
            portal,
        )
        self.assertIn(
            "Policy is a separate authority, not a Composition capability.",
            portal,
        )
        self.assertIn(
            "Integration selects reviewed Composition and Policy revisions by full commit SHA; Site adopts an exact Integration Bundle.",
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
