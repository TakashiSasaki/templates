from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

from scripts.glossary import TERM_ID


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "GLOSSARY_INVENTORY.md"
ID_CELL = re.compile(r"^`([^`]+)`$")
OWNER_CELL = re.compile(r"^(site|skill|policy|webapp)(?: curator)?$")
PROVIDERS = {"site", "skill", "policy", "webapp"}
REQUIRED_TABLES = {
    "Current canonical seed": {
        "id": "Canonical ID",
        "owner": "Owner / curator",
    },
    "Proposed first expansion": {
        "id": "Proposed ID",
        "owner": "Owner",
    },
    "Deferred repository candidates": {
        "id": "Proposed ID",
        "owner": "Likely owner",
    },
    "External terminology candidates": {
        "id": "Proposed ID",
        "owner": "Curator",
    },
}


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


class GlossaryInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = INVENTORY.read_text(encoding="utf-8").splitlines()

    def table(self, section: str) -> tuple[list[str], list[dict[str, str]]]:
        heading = f"## {section}"
        if heading not in self.lines:
            self.fail(f"missing inventory section: {heading}")
        heading_index = self.lines.index(heading)
        section_end = next(
            (
                index
                for index in range(heading_index + 1, len(self.lines))
                if self.lines[index].startswith("## ")
            ),
            len(self.lines),
        )

        table_index = next(
            (
                index
                for index in range(heading_index + 1, section_end)
                if self.lines[index].startswith("|")
            ),
            None,
        )
        self.assertIsNotNone(table_index, f"missing table in section: {heading}")
        assert table_index is not None

        header = _cells(self.lines[table_index])
        self.assertLess(table_index + 1, section_end)
        separator = _cells(self.lines[table_index + 1])
        self.assertEqual(len(separator), len(header))
        self.assertTrue(
            all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator),
            f"invalid Markdown table separator in section: {heading}",
        )

        rows: list[dict[str, str]] = []
        for line in self.lines[table_index + 2 : section_end]:
            if not line.startswith("|"):
                break
            values = _cells(line)
            self.assertEqual(
                len(values),
                len(header),
                f"column count mismatch in section: {heading}",
            )
            rows.append(dict(zip(header, values, strict=True)))

        self.assertTrue(rows, f"inventory table must not be empty: {heading}")
        return header, rows

    def test_glossary_inventory_candidate_ids_valid_and_unique(self) -> None:
        ids: list[str] = []

        for section, columns in REQUIRED_TABLES.items():
            header, rows = self.table(section)
            id_column = columns["id"]
            self.assertIn(id_column, header)

            for row in rows:
                raw_id = row[id_column]
                match = ID_CELL.fullmatch(raw_id)
                self.assertIsNotNone(
                    match,
                    f"{section} ID must be one backticked stable term ID: {raw_id!r}",
                )
                assert match is not None
                term_id = match.group(1)
                self.assertIsNotNone(
                    TERM_ID.fullmatch(term_id),
                    f"invalid stable term ID in {section}: {term_id}",
                )
                ids.append(term_id)

        duplicates = sorted(
            term_id for term_id, count in Counter(ids).items() if count > 1
        )
        self.assertEqual(duplicates, [])

    def test_glossary_inventory_structure_and_owners(self) -> None:
        for section, columns in REQUIRED_TABLES.items():
            header, rows = self.table(section)
            owner_column = columns["owner"]
            self.assertIn(owner_column, header)

            for row in rows:
                owner = row[owner_column]
                if section == "Current canonical seed":
                    self.assertIsNotNone(
                        OWNER_CELL.fullmatch(owner),
                        f"invalid owner/curator in {section}: {owner!r}",
                    )
                else:
                    self.assertIn(
                        owner,
                        PROVIDERS,
                        f"invalid owner/curator in {section}: {owner!r}",
                    )

        proposed_header, proposed_rows = self.table("Proposed first expansion")
        rationale_column = "Rationale / canonical source"
        self.assertIn(rationale_column, proposed_header)
        for row in proposed_rows:
            self.assertTrue(
                row[rationale_column].strip(),
                f"proposed term rationale must not be empty: {row}",
            )


if __name__ == "__main__":
    unittest.main()
