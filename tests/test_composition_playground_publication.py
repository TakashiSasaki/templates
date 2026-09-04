#!/usr/bin/env python3
"""Regression coverage for the published Composition Playground transport."""

from __future__ import annotations

import gzip
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

ASSET = ROOT / "generated" / "composition-playground-v1.json.gz"
CATALOG = ROOT / "docs" / "publication-catalog.json"


class CompositionPlaygroundPublicationTests(unittest.TestCase):
    def test_committed_transport_is_deterministic_and_semantically_current(self) -> None:
        current = ASSET.read_bytes()
        semantic_revision = publication.semantic_revision_from_gzip(ASSET)
        self.assertRegex(semantic_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(b"\x1f\x8b\x08", current[:3])
        self.assertEqual(b"\x00\x00\x00\x00", current[4:8], "gzip mtime must be zero")
        self.assertEqual(255, current[9], "gzip OS byte must be platform-neutral")
        self.assertEqual(
            publication.publication_bytes(semantic_revision=semantic_revision),
            current,
        )
        projection = json.loads(gzip.decompress(current))
        self.assertEqual(semantic_revision, projection["source"]["revision"])
        self.assertEqual("composition-playground-v1", projection["projection_id"])
        self.assertEqual(2336, sum(recipe["case_count"] for recipe in projection["recipes"]))

    def test_publication_provider_may_be_a_semantically_equivalent_descendant(self) -> None:
        semantic_revision = publication.semantic_revision_from_gzip(ASSET)
        provider_revision = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
        self.assertRegex(provider_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertNotEqual(
            semantic_revision,
            provider_revision,
            "this publication regression must cover a publication-only descendant",
        )
        self.assertEqual(
            publication.publication_bytes(semantic_revision=semantic_revision),
            ASSET.read_bytes(),
            "authoritative ancestry and semantic-path equivalence validation must accept the provider descendant",
        )

    def test_publication_catalog_registers_only_the_transport_asset(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        matches = [
            asset
            for asset in catalog["assets"]
            if asset["destination"].startswith("playground/")
        ]
        self.assertEqual(
            [
                {
                    "source": "generated/composition-playground-v1.json.gz",
                    "destination": "playground/composition-playground-v1.json.gz",
                    "optional": False,
                }
            ],
            matches,
        )

    def test_invalid_gzip_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            bad = Path(directory) / "bad.json.gz"
            bad.write_bytes(b"not-gzip")
            with self.assertRaises(CompositionError) as context:
                publication.semantic_revision_from_gzip(bad)
        self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", context.exception.code)


if __name__ == "__main__":
    unittest.main()
