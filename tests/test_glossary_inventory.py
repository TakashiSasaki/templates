from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

from scripts.glossary import TERM_ID


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "GLOSSARY_INVENTORY.md"
ID_CELL = re.compile(r"^`((?:templates|external)-[a-z0-9]+(?:-[a-z0-9]+)*)`$")


class GlossaryInventoryTests(unittest.TestCase):
    def inventory_ids(self) -> list[str]:
        ids: list[str] = []
        for line in INVENTORY.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            for cell in line.strip().strip("|").split("|"):
                match = ID_CELL.fullmatch(cell.strip())
                if match:
                    ids.append(match.group(1))
        return ids

    def test_glossary_inventory_candidate_ids_valid_and_unique(self) -> None:
        ids = self.inventory_ids()
        self.assertTrue(ids, "inventory must contain stable term IDs")

        invalid = [term_id for term_id in ids if TERM_ID.fullmatch(term_id) is None]
        self.assertEqual(invalid, [])

        duplicates = sorted(
            term_id for term_id, count in Counter(ids).items() if count > 1
        )
        self.assertEqual(duplicates, [])


if __name__ == "__main__":
    unittest.main()
