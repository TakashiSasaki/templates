from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import classify_publication_freshness as freshness  # noqa: E402


LOCKED = "0" * 40
CURRENT = "1" * 40


class PublicationFreshnessClassificationTests(unittest.TestCase):
    def test_equal_revisions_are_current(self) -> None:
        self.assertEqual("current", freshness.classify(LOCKED, LOCKED))

    def test_different_revisions_are_reported_without_being_invalid(self) -> None:
        self.assertEqual("different", freshness.classify(LOCKED, CURRENT))

    def test_invalid_revisions_are_rejected(self) -> None:
        invalid = (
            "composition",
            "A" * 40,
            "0" * 39,
            "0" * 41,
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(freshness.PublicationFreshnessError):
                    freshness.classify(value, CURRENT)
                with self.assertRaises(freshness.PublicationFreshnessError):
                    freshness.classify(LOCKED, value)

    def test_output_uses_github_output_key_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="publication-freshness-") as directory:
            output = Path(directory) / "output"
            freshness.write_relation(output, "different")
            freshness.write_relation(output, "current")

            self.assertEqual(
                "relation=different\nrelation=current\n",
                output.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
