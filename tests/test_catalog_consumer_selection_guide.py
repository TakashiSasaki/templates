from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CatalogConsumerSelectionGuideTests(unittest.TestCase):
    def test_catalog_explains_recipe_and_component_selection(self) -> None:
        guide = (ROOT / "catalog" / "README.md").read_text(encoding="utf-8")

        for required_text in (
            "## Consumer selection guide",
            "static/CDN Webapp",
            "`capability.mcp-apps`",
            "`lifecycle.release-bundle`",
            "Do not repeat transitive lifecycle dependencies",
            "Use `plan` before `apply`",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, guide)

    def test_recipe_summaries_expose_consumer_selection_boundaries(self) -> None:
        skill = json.loads((ROOT / "recipes" / "skill.json").read_text(encoding="utf-8"))
        webapp = json.loads(
            (ROOT / "recipes" / "webapp.json").read_text(encoding="utf-8")
        )

        self.assertIn("SKILL.md", skill["summary"])
        self.assertIn("explicit opt-ins", skill["summary"])
        self.assertIn("release lifecycle included transitively", webapp["summary"])
        self.assertIn("application capabilities remain explicit opt-ins", webapp["summary"])

    def test_webapp_keeps_release_lifecycle_transitive(self) -> None:
        webapp = json.loads(
            (ROOT / "recipes" / "webapp.json").read_text(encoding="utf-8")
        )
        artifact = json.loads(
            (ROOT / "components" / "artifact.webapp-core" / "component.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("lifecycle.release-bundle", artifact["requires"])
        self.assertTrue(
            all(
                component.startswith("capability.")
                for component in webapp["optional_components"]
            )
        )


if __name__ == "__main__":
    unittest.main()
