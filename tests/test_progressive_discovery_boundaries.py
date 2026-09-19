from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProgressiveDiscoveryBoundaryTests(unittest.TestCase):
    def test_adapter_names_authoritative_inventories_and_surface_ownership(self) -> None:
        adapter = json.loads((ROOT / ".progressive-discovery.json").read_text(encoding="utf-8"))

        self.assertEqual(adapter["root_index"], "index.md")
        self.assertIn("catalog/catalog.json", adapter["authoritative_inventories"])
        self.assertIn("docs/publication-catalog.json", adapter["authoritative_inventories"])
        self.assertIn("components", adapter["closed_inventories"])
        self.assertIn("generated", adapter["explicit_exclusions"])
        self.assertEqual(adapter["curated_shortcuts"], ["docs"])
        self.assertTrue(adapter["publication_system"])
        self.assertEqual(
            adapter["surface_boundaries"]["provider-maintenance"],
            ["docs/provider-maintenance.md", "docs/publication-catalog.md"],
        )
        self.assertEqual(
            adapter["surface_boundaries"]["consumer-distributed"],
            ["docs/consumer-guide.md", "skills/composition/SKILL.md"],
        )

    def test_root_routes_through_meaningful_boundaries(self) -> None:
        text = (ROOT / "index.md").read_text(encoding="utf-8")
        for target in ("docs/index.md", "catalog/index.md", "recipes/index.md", "schemas/index.md", "release/index.md"):
            with self.subTest(target=target):
                self.assertIn(f"]({target})", text)
        self.assertNotIn("](components/)", text)
        self.assertIn("](examples/README.md)", text)

    def test_nested_indexes_are_small_curated_navigation_surfaces(self) -> None:
        for relative in ("index.md", "docs/index.md", "catalog/index.md", "recipes/index.md", "schemas/index.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# "), relative)
            self.assertNotIn("git_sha", text)
            self.assertNotIn("timestamp", text)


if __name__ == "__main__":
    unittest.main()
