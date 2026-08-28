from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
INDEX = ROOT / "docs" / "index.md"
ENTRY = ROOT / "docs" / "evaluation-guide.md"
CATALOG = ROOT / "docs" / "publication-catalog.json"
PROTOCOL = ROOT / "examples" / "evaluations" / "small-model-clean-room-protocol.txt"
SCORECARD = ROOT / "examples" / "evaluations" / "evaluation-scorecard.txt"
SCHEMA = ROOT / "examples" / "evaluations" / "evaluation-scorecard.schema.json"
JA_README = ROOT / "translations" / "ja" / "README.md"
JA_INDEX = ROOT / "translations" / "ja" / "docs" / "index.md"
JA_ENTRY = ROOT / "translations" / "ja" / "docs" / "evaluation-guide.md"
LINK_TARGET = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class EvaluationEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry_text = ENTRY.read_text(encoding="utf-8")
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_normal_authority_entries_discover_evaluation_guide(self) -> None:
        self.assertIn(
            "[Evaluating Composition](docs/evaluation-guide.md)",
            README.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "[Evaluating Composition](evaluation-guide.md)",
            INDEX.read_text(encoding="utf-8"),
        )

    def test_japanese_authority_entries_discover_evaluation_guide(self) -> None:
        self.assertIn(
            "[Evaluating Composition](docs/evaluation-guide.md)",
            JA_README.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "[Composition の評価](evaluation-guide.md)",
            JA_INDEX.read_text(encoding="utf-8"),
        )
        translated_guide = JA_ENTRY.read_text(encoding="utf-8")
        for target in (
            "../../../examples/evaluations/small-model-clean-room-protocol.txt",
            "../../../examples/evaluations/evaluation-scorecard.txt",
            "../../../examples/evaluations/evaluation-scorecard.schema.json",
        ):
            with self.subTest(target=target):
                self.assertIn(target, translated_guide)

    def test_japanese_guide_links_exact_existing_authorities(self) -> None:
        expected = {PROTOCOL.resolve(), SCORECARD.resolve(), SCHEMA.resolve()}
        actual = {
            (JA_ENTRY.parent / target).resolve()
            for target in LINK_TARGET.findall(JA_ENTRY.read_text(encoding="utf-8"))
        }
        self.assertEqual(actual, expected)
        self.assertTrue(all(path.is_file() for path in actual))

    def test_guide_orders_protocol_scorecard_schema_and_output(self) -> None:
        protocol = "../examples/evaluations/small-model-clean-room-protocol.txt"
        scorecard = "../examples/evaluations/evaluation-scorecard.txt"
        schema = "../examples/evaluations/evaluation-scorecard.schema.json"
        self.assertLess(self.entry_text.index(protocol), self.entry_text.index(scorecard))
        self.assertLess(self.entry_text.index(scorecard), self.entry_text.index(schema))
        self.assertLess(
            self.entry_text.index(schema),
            self.entry_text.index("The output is the validated scorecard JSON"),
        )

    def test_guide_links_exact_existing_authorities(self) -> None:
        expected = {PROTOCOL.resolve(), SCORECARD.resolve(), SCHEMA.resolve()}
        actual = {
            (ENTRY.parent / target).resolve()
            for target in LINK_TARGET.findall(self.entry_text)
        }
        self.assertEqual(actual, expected)
        self.assertTrue(all(path.is_file() for path in actual))

    def test_publication_catalog_exposes_guide_and_supporting_assets(self) -> None:
        documents = {
            entry["id"]: entry["source"]
            for entry in self.catalog["documents"]
        }
        self.assertEqual(documents["evaluation-guide"], "docs/evaluation-guide.md")
        assets = {
            entry["source"]: entry["destination"]
            for entry in self.catalog["assets"]
        }
        self.assertEqual(
            {source: assets[source] for source in (
                "examples/evaluations/small-model-clean-room-protocol.txt",
                "examples/evaluations/evaluation-scorecard.txt",
                "examples/evaluations/evaluation-scorecard.schema.json",
            )},
            {
                "examples/evaluations/small-model-clean-room-protocol.txt":
                    "evaluation/small-model-clean-room-protocol.txt",
                "examples/evaluations/evaluation-scorecard.txt":
                    "evaluation/evaluation-scorecard.txt",
                "examples/evaluations/evaluation-scorecard.schema.json":
                    "evaluation/evaluation-scorecard.schema.json",
            },
        )

    def test_entrypoint_keeps_evaluator_and_consumer_authorities_separate(self) -> None:
        for phrase in (
            "not for ordinary consumer installation or product implementation",
            "not materialized into ordinary consumer repositories",
            "do not add an evaluator mode",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.entry_text)


if __name__ == "__main__":
    unittest.main()
