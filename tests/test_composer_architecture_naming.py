from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs" / "architecture" / "composer-mvp.md"
ARCHITECTURE_JA = (
    ROOT / "translations" / "ja" / "docs" / "architecture" / "composer-mvp.md"
)
INDEX = ROOT / "docs" / "index.md"
INDEX_JA = ROOT / "translations" / "ja" / "docs" / "index.md"
PUBLICATION_CATALOG = ROOT / "docs" / "publication-catalog.json"


class ComposerArchitectureNamingTests(unittest.TestCase):
    def test_reader_facing_surfaces_use_architecture_not_mvp(self) -> None:
        architecture_heading = ARCHITECTURE.read_text(encoding="utf-8").splitlines()[0]
        architecture_ja_heading = ARCHITECTURE_JA.read_text(encoding="utf-8").splitlines()[0]
        index = INDEX.read_text(encoding="utf-8")
        index_ja = INDEX_JA.read_text(encoding="utf-8")

        self.assertEqual(
            architecture_heading,
            "# Composer architecture and managed-state contract",
        )
        self.assertEqual(
            architecture_ja_heading,
            "# Composer architecture と managed-state contract",
        )
        self.assertIn("[Composer architecture](architecture/composer-mvp.md)", index)
        self.assertIn("[Composer architecture](architecture/composer-mvp.md)", index_ja)
        self.assertNotIn("Composer MVP", architecture_heading)
        self.assertNotIn("Composer MVP", architecture_ja_heading)
        self.assertNotIn("[Composer MVP]", index)
        self.assertNotIn("[Composer MVP]", index_ja)

    def test_reader_documentation_does_not_expose_mvp_link_label(self) -> None:
        reader_roots = (ROOT / "docs", ROOT / "translations")
        for reader_root in reader_roots:
            for path in sorted(reader_root.rglob("*.md")):
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertNotIn(
                        "[Composer MVP]",
                        path.read_text(encoding="utf-8"),
                    )

    def test_legacy_publication_identity_is_not_reader_facing_semantics(self) -> None:
        catalog = json.loads(PUBLICATION_CATALOG.read_text(encoding="utf-8"))
        documents = {entry["id"]: entry for entry in catalog["documents"]}

        self.assertEqual(
            documents["composer-mvp"]["source"],
            "docs/architecture/composer-mvp.md",
        )


if __name__ == "__main__":
    unittest.main()
