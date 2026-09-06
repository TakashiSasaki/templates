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

GENERATED = ROOT / "generated"
CATALOG = ROOT / "docs" / "publication-catalog.json"


class CompositionPlaygroundPublicationTests(unittest.TestCase):
    def test_manifest_pins_exact_semantic_source_and_asset_inventory(self) -> None:
        manifest = publication.read_publication_manifest(GENERATED)
        self.assertRegex(str(manifest["semantic_revision"]), re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(
            [publication.BASE_NAME, publication.INTENT_NAME],
            manifest["assets"],
        )

    def test_generated_assets_are_deterministic_and_bounded(self) -> None:
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        payloads = publication.publication_payloads(semantic_revision=semantic_revision)
        base = payloads[publication.BASE_NAME]
        intent = payloads[publication.INTENT_NAME]
        self.assertEqual(b"\x1f\x8b", base[:2])
        self.assertEqual(b"\x1f\x8b", intent[:2])
        base_projection = json.loads(gzip.decompress(base))
        intent_projection = json.loads(gzip.decompress(intent))
        self.assertEqual("composition-playground-v1", base_projection["projection_id"])
        self.assertEqual("composition-playground-intent-v1", intent_projection["projection_id"])
        self.assertEqual(semantic_revision, base_projection["source"]["revision"])
        self.assertEqual(semantic_revision, intent_projection["source"]["revision"])
        self.assertEqual(2624, sum(recipe["case_count"] for recipe in base_projection["recipes"]))
        self.assertLess(len(base), 131_072)
        self.assertLess(len(intent), 131_072)
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            target = Path(directory)
            (target / publication.MANIFEST_NAME).write_bytes((GENERATED / publication.MANIFEST_NAME).read_bytes())
            publication.write_directory(target)
            self.assertEqual(semantic_revision, publication.check_directory(target))

    def test_publication_provider_may_be_semantically_equivalent_descendant(self) -> None:
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        provider_revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        self.assertRegex(provider_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertNotEqual(semantic_revision, provider_revision)

    def test_publication_catalog_declares_materialized_projection_assets(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        matches = [asset for asset in catalog["assets"] if asset["destination"].startswith("playground/composition-playground")]
        self.assertEqual([
            {"source": "generated/composition-playground-v1.json.gz", "destination": "playground/composition-playground-v1.json.gz", "optional": False},
            {"source": "generated/composition-playground-intent-v1.json.gz", "destination": "playground/composition-playground-intent-v1.json.gz", "optional": False},
        ], matches)

    def test_invalid_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            target = Path(directory)
            (target / publication.MANIFEST_NAME).write_text("not-json", encoding="utf-8")
            with self.assertRaises(CompositionError) as context:
                publication.semantic_revision_from_manifest(target)
        self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", context.exception.code)


if __name__ == "__main__":
    unittest.main()
