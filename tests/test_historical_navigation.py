from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "site-manifest.json"


def _walk_navigation(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    for item in items:
        children = item.get("children")
        if isinstance(children, list):
            leaves.extend(_walk_navigation(children))
        else:
            leaves.append(item)
    return leaves


class HistoricalNavigationTests(unittest.TestCase):
    def test_composition_exposes_only_consolidated_authority_history(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        composition = next(
            node
            for node in manifest["navigation"]
            if node["title"] == "Composition"
        )
        history = next(
            child
            for child in composition["children"]
            if child.get("title") == "Historical provenance"
        )
        self.assertEqual(
            history["children"],
            [
                {
                    "title": "Authority migration history",
                    "publication": "composition",
                    "document": "composition-authority-migration",
                    "destination": "composition/migrations/authority-migration.md",
                }
            ],
        )
        self.assertFalse(
            any(
                node.get("title") == "Composition migration history"
                for node in manifest["navigation"]
            )
        )

    def test_stage_notes_do_not_reenter_reader_navigation(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        leaves = _walk_navigation(manifest["navigation"])
        document_ids = {item.get("document") for item in leaves}

        self.assertIn("composition-authority-migration", document_ids)
        self.assertNotIn("skill-capability-migration", document_ids)
        self.assertNotIn("webapp-lifecycle-migration", document_ids)

    def test_actionable_domain_migrations_remain_reader_navigation(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        leaves = _walk_navigation(manifest["navigation"])
        documents = {item.get("document"): item for item in leaves}

        self.assertEqual(
            documents["web-routes-v1-migration"]["destination"],
            "web/migrations/routes-v1-to-v2.md",
        )
        self.assertEqual(
            documents["web-routes-v2-migration"]["destination"],
            "web/migrations/routes-v2-to-v3.md",
        )
        self.assertEqual(
            documents["web-routes-v3-migration"]["destination"],
            "web/migrations/routes-v3-to-v4.md",
        )
        self.assertNotIn("routes-migration", documents)
        self.assertNotIn("routes-v3-migration", documents)
        self.assertEqual(
            documents["ui-states-migration"]["destination"],
            "webapp/docs/migrations/ui-states-v1-to-v2.md",
        )
        self.assertEqual(
            documents["surfaces-v2-migration"]["destination"],
            "webapp/docs/migrations/surfaces-v1-to-v2.md",
        )


if __name__ == "__main__":
    unittest.main()
