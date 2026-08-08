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
    def test_portal_cover_is_reader_oriented_and_exposes_all_publications(self) -> None:
        portal = PORTAL_HOME.read_text(encoding="utf-8")

        self.assertIn('href="overview/"', portal)
        for destination in ("skill/", "policy/", "webapp/"):
            with self.subTest(destination=destination):
                self.assertIn(f'href="{destination}"', portal)
        for label in ("Skill", "Policy", "Web application"):
            with self.subTest(label=label):
                self.assertIn(
                    f'class="portal-domain-card__label">{label}</span>',
                    portal,
                )

    def test_portal_overview_preserves_publication_policy_explanation(self) -> None:
        overview = PORTAL_OVERVIEW.read_text(encoding="utf-8")

        self.assertIn("explicit allowlists", overview)
        self.assertIn("full 40-character commit SHAs", overview)
        self.assertIn("build-provenance.json", overview)
        self.assertIn("Machine-readable contracts and schemas", overview)

    def test_portal_and_policy_include_all_top_level_entry_points(self) -> None:
        policy = " ".join(PUBLISHING_POLICY.read_text(encoding="utf-8").split())
        overview = " ".join(PORTAL_OVERVIEW.read_text(encoding="utf-8").split())

        self.assertIn(
            "- `/`, `/skill/`, `/policy/`, and `/webapp/` are reachable;",
            policy,
        )
        self.assertIn(
            "under `/skill/`, `/policy/`, and `/webapp/`.",
            overview,
        )

    def test_policy_does_not_render_site_only_as_a_list_item(self) -> None:
        raw_policy = PUBLISHING_POLICY.read_text(encoding="utf-8")
        normalized_policy = " ".join(raw_policy.split())

        self.assertNotIn("\n-only deployment boundary", raw_policy)
        self.assertIn("`site`-only deployment boundary", normalized_policy)

    def test_integrated_navigation_has_stable_portal_and_provider_entry_points(self) -> None:
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
        self.assertEqual(indexed[("skill", "overview")], "skill/index.md")
        self.assertEqual(indexed[("policy", "overview")], "policy/index.md")
        self.assertEqual(indexed[("webapp", "overview")], "webapp/index.md")

        top_level_titles = [node["title"] for node in manifest["navigation"]]
        self.assertIn("Portal overview", top_level_titles)
        self.assertIn("Skill", top_level_titles)
        self.assertIn("Policy", top_level_titles)
        self.assertIn("Web application", top_level_titles)

    def test_provider_inputs_are_locked_to_full_commit_shas(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(
            set(lock["publications"]),
            {"skill", "policy", "webapp"},
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

    def test_deployment_environment_is_documented_as_an_external_release_gate(self) -> None:
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
