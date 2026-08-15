from __future__ import annotations

import unittest
from pathlib import Path

from scripts.glossary import load_glossary

ROOT = Path(__file__).resolve().parents[1]


class SiteGlossaryFirstExpansionTests(unittest.TestCase):
    def test_site_glossary_contains_reviewed_first_expansion_terms(self) -> None:
        terms = load_glossary(ROOT / "docs/glossary.yml")
        by_id = {term["id"]: term for term in terms}

        integrated = by_id["templates-integrated-publication"]
        self.assertEqual(integrated["term"], "Integrated publication")
        self.assertEqual(integrated["origin"], "repository")
        self.assertEqual(integrated["localized_labels"]["ja"]["term"], "統合公開")
        self.assertIn("templates-provider-branch", integrated["related_terms"])
        self.assertIn("templates-publication-catalog", integrated["related_terms"])
        self.assertIn("templates-publication-source-lock", integrated["related_terms"])

        source_lock = by_id["templates-publication-source-lock"]
        self.assertEqual(source_lock["term"], "Publication source lock")
        self.assertEqual(source_lock["origin"], "repository")
        self.assertEqual(source_lock["localized_labels"]["ja"]["term"], "公開ソースロック")
        self.assertIn("full 40-character commit SHA", source_lock["definition"])
        self.assertIn("templates-provider-branch", source_lock["related_terms"])
        self.assertIn("templates-integrated-publication", source_lock["related_terms"])


if __name__ == "__main__":
    unittest.main()
