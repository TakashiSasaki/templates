from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs" / "architecture"
CATALOG_ARCHITECTURE = ARCHITECTURE / "catalog.md"
PR_STAGE = re.compile(r"\bPR(?:\s*#?\s*)?\d+\b")


class ReaderArchitectureTests(unittest.TestCase):
    def test_current_architecture_uses_semantic_names_not_pr_stages(self) -> None:
        paths = sorted(ARCHITECTURE.glob("*.md"))
        self.assertTrue(paths)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIsNone(
                    PR_STAGE.search(text),
                    "current-state architecture must use semantic concepts; "
                    "PR chronology belongs in migration/provenance documentation",
                )

    def test_catalog_architecture_describes_current_resolution_boundary(self) -> None:
        text = CATALOG_ARCHITECTURE.read_text(encoding="utf-8")

        for stale_claim in (
            "The later resolver will",
            "Later artifact/lifecycle migrations",
            "remain future work",
            "## Relation to PR1 wording",
        ):
            with self.subTest(stale_claim=stale_claim):
                self.assertNotIn(stale_claim, text)

        self.assertIn("## Catalog and consumer resolution", text)
        self.assertIn("The production catalog and the Composer have separate responsibilities.", text)
        self.assertIn(".template-composition/lock.json", text)
        self.assertIn("`initial` composition", text)
        self.assertIn("`update` reuses the normalized intent", text)
        self.assertIn("`upgrade` accepts explicit replacement intent", text)


if __name__ == "__main__":
    unittest.main()
