from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONCEPTS = ROOT / "docs" / "guides" / "composition-concepts.md"
JA_CONCEPTS = ROOT / "translations" / "ja" / "docs" / "guides" / "composition-concepts.md"
DOC_INDEX = ROOT / "docs" / "index.md"
JA_DOC_INDEX = ROOT / "translations" / "ja" / "docs" / "index.md"
PUBLICATION_CATALOG = ROOT / "docs" / "publication-catalog.json"
TRANSLATION_MANIFEST = ROOT / "translations" / "manifest.json"


class CompositionConceptsGuideTests(unittest.TestCase):
    def test_guide_is_explicitly_explanatory_and_optional(self) -> None:
        guide = CONCEPTS.read_text(encoding="utf-8")
        self.assertIn("explanatory guide", guide)
        self.assertIn("not a second semantic authority", guide)
        self.assertIn("do **not** need to read this page", guide)
        self.assertIn("Canonical repository terminology remains in `docs/glossary.yml`", guide)

    def test_guide_disambiguates_repository_specific_common_words(self) -> None:
        guide = CONCEPTS.read_text(encoding="utf-8")
        for phrase in (
            "Recipe",
            "Artifact component",
            "Component",
            "Contract",
            "Seed material",
            "Composition lock",
            "Artifact component is not Artifact contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

    def test_documentation_index_keeps_task_first_entry_before_concepts(self) -> None:
        index = DOC_INDEX.read_text(encoding="utf-8")
        walkthrough = index.index("[Webapp product walkthrough]")
        concepts = index.index("[Composition concepts for first-time readers]")
        self.assertLess(walkthrough, concepts)
        self.assertIn("You do not need to read it before following a first-use walkthrough", index)

    def test_concepts_guide_is_a_declared_publication_document(self) -> None:
        catalog = json.loads(PUBLICATION_CATALOG.read_text(encoding="utf-8"))
        documents = {entry["id"]: entry for entry in catalog["documents"]}
        self.assertEqual(
            documents["composition-concepts"],
            {
                "id": "composition-concepts",
                "source": "docs/guides/composition-concepts.md",
                "optional": False,
                "home": False,
            },
        )

    def test_japanese_reference_translation_is_registered_and_optional_to_first_use(self) -> None:
        translation = JA_CONCEPTS.read_text(encoding="utf-8")
        self.assertIn("参考訳（非正本）", translation)
        self.assertIn("読む必要は **ありません**", translation)

        ja_index = JA_DOC_INDEX.read_text(encoding="utf-8")
        self.assertLess(
            ja_index.index("[Webapp product walkthrough]"),
            ja_index.index("[初見者向け Composition concepts]"),
        )

        manifest = json.loads(TRANSLATION_MANIFEST.read_text(encoding="utf-8"))
        entries = {
            (entry["canonical"], entry["language"]): entry
            for entry in manifest["translations"]
        }
        self.assertEqual(
            entries[("docs/guides/composition-concepts.md", "ja")]["translation"],
            "translations/ja/docs/guides/composition-concepts.md",
        )


if __name__ == "__main__":
    unittest.main()
