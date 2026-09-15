from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import site_website_contract as website
from scripts.generate_repository_trees import RepositoryTreeError, manifest_destinations
from scripts.prepare_repository_tree_publication import PreparationError, prepare

ROOT = Path(__file__).resolve().parents[1]


class CanonicalManifestConsumerBoundaryTests(unittest.TestCase):
    def production_manifest(self):
        return json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))

    def write_manifest(self, root, manifest):
        root.mkdir(parents=True, exist_ok=True)
        (root / "site-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def invalid_manifests(self):
        incomplete = self.production_manifest()
        incomplete.pop("audiences")
        malformed = self.production_manifest()
        malformed["documents"][1].pop("primary_audience")
        unsafe = self.production_manifest()
        unsafe["documents"][1]["destination"] = "../outside.md"
        return (
            ("incomplete", incomplete),
            ("malformed", malformed),
            ("unsafe", unsafe),
        )

    def test_website_projection_uses_complete_canonical_validation(self):
        for label, manifest in self.invalid_manifests():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copy2(ROOT / "zensical.template.toml", root / "zensical.template.toml")
                self.write_manifest(root, manifest)
                with self.assertRaises(ValueError):
                    website.documents(root)

    def test_repository_tree_projection_uses_complete_canonical_validation(self):
        for label, manifest in self.invalid_manifests():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_manifest(root, manifest)
                with self.assertRaises(RepositoryTreeError):
                    manifest_destinations(root)

    def test_preparation_rejects_before_output_creation(self):
        for label, manifest in self.invalid_manifests():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "site"
                output = Path(tmp) / "prepared"
                self.write_manifest(root, manifest)
                with self.assertRaises(PreparationError):
                    prepare(root, output)
                self.assertFalse(output.exists())

    def test_preparation_preserves_existing_output_before_rejection(self):
        manifest = self.production_manifest()
        manifest["documents"][1]["destination"] = "../outside.md"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            output = Path(tmp) / "prepared"
            self.write_manifest(root, manifest)
            output.mkdir()
            sentinel = output / "existing.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")

            with self.assertRaises(PreparationError):
                prepare(root, output)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")


if __name__ == "__main__":
    unittest.main()
