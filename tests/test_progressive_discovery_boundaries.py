from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProgressiveDiscoveryBoundaryTests(unittest.TestCase):
    def test_policy_adapter_uses_profiles_and_publication_as_inventories(self) -> None:
        adapter = json.loads((ROOT / ".progressive-discovery.json").read_text(encoding="utf-8"))

        self.assertEqual(adapter["root_index"], "index.md")
        self.assertIn("docs/publication-catalog.json", adapter["authoritative_inventories"])
        self.assertIn("profiles/progressive-discovery.yml", adapter["authoritative_inventories"])
        self.assertIn("schemas", adapter["explicit_exclusions"])
        self.assertEqual(adapter["surface_boundaries"]["consumer-distributed"], [
            "docs/consumer/index.md",
            "skills/agent-policy/SKILL.md",
        ])

    def test_root_routes_through_policy_profile_and_skill_boundaries(self) -> None:
        text = (ROOT / "index.md").read_text(encoding="utf-8")
        for target in ("docs/index.md", "policy/index.md", "profiles/index.md", "skills/index.md"):
            with self.subTest(target=target):
                self.assertIn(f"]({target})", text)

    def test_policy_family_indexes_are_authored_navigation(self) -> None:
        for relative in (
            "index.md",
            "policy/index.md",
            "policy/core/index.md",
            "policy/progressive-discovery/index.md",
            "profiles/index.md",
            "skills/index.md",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# "), relative)
            self.assertNotIn("git_sha", text)
            self.assertNotIn("timestamp", text)

    def test_policy_adapter_excludes_non_document_assets_from_expected_coverage(self) -> None:
        adapter = json.loads((ROOT / ".progressive-discovery.json").read_text(encoding="utf-8"))
        self.assertIn("skills/pr-review/references", adapter["explicit_exclusions"])


if __name__ == "__main__":
    unittest.main()
