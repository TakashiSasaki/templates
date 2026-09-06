#!/usr/bin/env python3
"""Regression coverage for published Composition Playground projections."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_composition_playground_publication as publication  # noqa: E402
from composer_core_impl import CompositionError  # noqa: E402

GENERATED = ROOT / "generated"
CATALOG = ROOT / "docs" / "publication-catalog.json"


class CompositionPlaygroundPublicationTests(unittest.TestCase):
    def test_committed_assets_are_deterministic_and_semantically_current(self) -> None:
        base = GENERATED / publication.BASE_NAME
        intent = GENERATED / publication.INTENT_NAME
        semantic_revision = publication.semantic_revision_from_json(base)
        self.assertRegex(semantic_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(semantic_revision, publication.semantic_revision_from_json(intent))
        expected = publication.publication_payloads(semantic_revision=semantic_revision)
        self.assertEqual(expected[publication.BASE_NAME], base.read_bytes())
        self.assertEqual(expected[publication.INTENT_NAME], intent.read_bytes())
        projection = json.loads(base.read_text(encoding="utf-8"))
        self.assertEqual("composition-playground-v1", projection["projection_id"])
        self.assertEqual(2624, sum(recipe["case_count"] for recipe in projection["recipes"]))
        self.assertLess(base.stat().st_size, 1_048_576)
        self.assertLess(intent.stat().st_size, 524_288)

    def test_publication_provider_may_be_semantically_equivalent_descendant(self) -> None:
        base = GENERATED / publication.BASE_NAME
        semantic_revision = publication.semantic_revision_from_json(base)
        provider_revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        self.assertRegex(provider_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertNotEqual(semantic_revision, provider_revision)
        self.assertEqual(semantic_revision, publication.check_directory(GENERATED))

    def test_publication_catalog_registers_both_projection_assets(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        matches = [asset for asset in catalog["assets"] if asset["destination"].startswith("playground/composition-playground")]
        self.assertEqual([
            {"source": "generated/composition-playground-v1.json", "destination": "playground/composition-playground-v1.json", "optional": False},
            {"source": "generated/composition-playground-intent-v1.json", "destination": "playground/composition-playground-intent-v1.json", "optional": False},
        ], matches)

    def test_invalid_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            bad = Path(directory) / publication.BASE_NAME
            bad.write_text("not-json", encoding="utf-8")
            with self.assertRaises(CompositionError) as context:
                publication.semantic_revision_from_json(bad)
        self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", context.exception.code)


if __name__ == "__main__":
    unittest.main()
