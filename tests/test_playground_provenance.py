from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.validate_playground_provenance import ProvenanceError, validate_publication, validate_projections


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "generated"


class PlaygroundProvenanceTests(unittest.TestCase):
    def test_current_publication_binds_base_intent_and_manifest(self) -> None:
        revision = validate_publication(GENERATED)
        self.assertRegex(revision, r"^[0-9a-f]{40}$")

    def test_projection_pair_rejects_mismatched_source_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.json"
            intent = root / "intent.json"
            base.write_text(
                json.dumps({"projection_id": "composition-playground-v1", "source": {"revision": "a" * 40}}),
                encoding="utf-8",
            )
            intent.write_text(
                json.dumps({"projection_id": "composition-playground-intent-v1", "source": {"revision": "b" * 40}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProvenanceError, "revisions differ"):
                validate_projections((base, intent))

    def test_publication_rejects_a_stale_projection_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated"
            docs = root / "docs"
            shutil.copytree(GENERATED, generated)
            shutil.copytree(ROOT / "docs", docs)
            path = generated / "composition-playground-v1.json.gz"
            value = json.loads(gzip.decompress(path.read_bytes()))
            value["source"]["revision"] = "f" * 40
            path.write_bytes(gzip.compress(json.dumps(value).encode("utf-8")))
            with self.assertRaisesRegex(ProvenanceError, "semantic revision"):
                validate_publication(generated)

    def test_publication_rejects_missing_catalog_asset_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated"
            docs = root / "docs"
            shutil.copytree(GENERATED, generated)
            shutil.copytree(ROOT / "docs", docs)
            catalog_path = docs / "publication-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["assets"] = [
                asset
                for asset in catalog["assets"]
                if not str(asset.get("destination", "")).startswith("playground/composition-playground")
            ]
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(ProvenanceError, "catalog"):
                validate_publication(generated)


if __name__ == "__main__":
    unittest.main()
