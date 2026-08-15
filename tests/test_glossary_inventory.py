from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

from scripts.glossary import ORIGINS, REPOSITORY_TERM_ID, TERM_ID


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "GLOSSARY_INVENTORY.md"
ID_CELL = re.compile(r"^`([^`]+)`$")
PROVIDERS = {"site", "skill", "policy", "webapp"}
OWNER_CELL = re.compile(
    rf"^({'|'.join(re.escape(provider) for provider in sorted(PROVIDERS))})(?: curator)?$"
)
REQUIRED_TABLES = {
    "Original canonical seed": {
        "id": "Canonical ID",
        "owner": "Owner / curator",
    },
    "Completed first expansion": {
        "id": "Canonical ID",
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
EXPECTED_FIRST_EXPANSION_IDS = {
    "templates-integrated-publication",
    "templates-publication-source-lock",
    "templates-skill-runtime-decision-record",
    "templates-skill-public-interface-selection-contract",
    "templates-shared-policy",
    "templates-context-policy",
    "templates-repository-local-policy",
    "templates-artifact-contract",
    "templates-adapter-renderer-requirement",
    "templates-explanatory-material",
    "templates-policy-override",
    "templates-webapp-template-source-artifact",
    "templates-webapp-template-distribution-artifact",
    "templates-webapp-product-repository-artifact",
    "templates-webapp-product-mode",
    "templates-webapp-release-bundle",
    "templates-webapp-contract-family",
}
EXPECTED_CROSS_PROVIDER_RELATIONS = {
    ("templates-skill-profile", "templates-policy-profile"),
    ("templates-policy-profile", "templates-skill-profile"),
    (
        "templates-skill-public-interface-selection-contract",
        "templates-artifact-contract",
    ),
    (
        "templates-skill-public-interface-selection-contract",
        "templates-adapter-renderer-requirement",
    ),
    ("templates-webapp-implementation-evidence", "templates-artifact-contract"),
    ("templates-webapp-release-evidence", "templates-artifact-contract"),
    ("templates-webapp-release-bundle", "templates-artifact-contract"),
}


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _term_id(cell: str, *, context: str) -> str:
    match = ID_CELL.fullmatch(cell)
    if match is None:
        raise AssertionError(
            f"{context} must be one backticked stable term ID: {cell!r}"
        )
    return match.group(1)


class GlossaryInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = INVENTORY.read_text(encoding="utf-8").splitlines()

    def table(
        self,
        section: str,
        *,
        heading_level: int = 2,
    ) -> tuple[list[str], list[dict[str, str]]]:
        heading_prefix = "#" * heading_level
        heading = f"{heading_prefix} {section}"
        if heading not in self.lines:
            self.fail(f"missing inventory section: {heading}")
        heading_index = self.lines.index(heading)
        section_end = next(
            (
                index
                for index in range(heading_index + 1, len(self.lines))
                if re.match(rf"^#{{1,{heading_level}}} ", self.lines[index])
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
                term_id = _term_id(
                    row[id_column],
                    context=f"{section} ID",
                )
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
                if section == "Original canonical seed":
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

                if "Origin" in row:
                    self.assertIn(
                        row["Origin"],
                        ORIGINS,
                        f"invalid origin in {section}: {row['Origin']!r}",
                    )

        completed_header, completed_rows = self.table("Completed first expansion")
        rationale_column = "Rationale / canonical source"
        self.assertIn(rationale_column, completed_header)
        for row in completed_rows:
            self.assertTrue(
                row[rationale_column].strip(),
                f"completed term rationale must not be empty: {row}",
            )

    def test_glossary_inventory_completed_expansion_metadata(self) -> None:
        header, rows = self.table("Completed first expansion")
        for column in (
            "Canonical term",
            "Canonical ID",
            "Owner",
            "Origin",
            "Japanese discovery label",
            "Rationale / canonical source",
        ):
            self.assertIn(column, header)

        ids: set[str] = set()
        for row in rows:
            self.assertEqual(row["Origin"], "repository")
            self.assertTrue(
                row["Canonical term"].strip(),
                f"canonical term must not be empty: {row}",
            )
            self.assertTrue(
                row["Japanese discovery label"].strip(),
                f"Japanese discovery label must not be empty: {row}",
            )

            term_id = _term_id(
                row["Canonical ID"],
                context="completed first-expansion ID",
            )
            self.assertIsNotNone(
                REPOSITORY_TERM_ID.fullmatch(term_id),
                f"first-expansion term must use a repository ID: {term_id}",
            )
            ids.add(term_id)

        self.assertEqual(ids, EXPECTED_FIRST_EXPANSION_IDS)
        self.assertEqual(len(rows), len(EXPECTED_FIRST_EXPANSION_IDS))

    def test_glossary_inventory_records_completed_relation_pass(self) -> None:
        header, rows = self.table(
            "Completed first cross-provider relation pass",
            heading_level=3,
        )
        self.assertEqual(
            header,
            ["Source term", "Related term", "Relation rationale"],
        )

        relations: set[tuple[str, str]] = set()
        for row in rows:
            source = _term_id(row["Source term"], context="relation source")
            target = _term_id(row["Related term"], context="relation target")
            self.assertIsNotNone(TERM_ID.fullmatch(source))
            self.assertIsNotNone(TERM_ID.fullmatch(target))
            self.assertNotEqual(source, target)
            self.assertTrue(
                row["Relation rationale"].strip(),
                f"relation rationale must not be empty: {row}",
            )
            relations.add((source, target))

        self.assertEqual(relations, EXPECTED_CROSS_PROVIDER_RELATIONS)
        self.assertEqual(len(rows), len(EXPECTED_CROSS_PROVIDER_RELATIONS))


if __name__ == "__main__":
    unittest.main()
