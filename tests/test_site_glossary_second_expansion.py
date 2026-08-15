from __future__ import annotations

import unittest
from pathlib import Path

from scripts.glossary import load_glossary


ROOT = Path(__file__).resolve().parents[1]


class SiteGlossarySecondExpansionTests(unittest.TestCase):
    def test_site_glossary_contains_index_guided_navigation(self) -> None:
        terms = load_glossary(ROOT / "docs/glossary.yml")
        by_id = {term["id"]: term for term in terms}

        guided = by_id["templates-index-guided-navigation"]
        self.assertEqual(guided["term"], "Index-guided navigation")
        self.assertEqual(guided["origin"], "repository")
        self.assertEqual(
            guided["localized_labels"]["ja"]["term"],
            "インデックス誘導ナビゲーション",
        )
        self.assertIn("/guided/", guided["definition"])
        self.assertIn("/guided/graph.json", guided["definition"])
        self.assertEqual(
            set(guided["related_terms"]),
            {
                "templates-integrated-publication",
                "templates-provider-branch",
                "templates-publication-catalog",
                "templates-publication-source-lock",
            },
        )


if __name__ == "__main__":
    unittest.main()
