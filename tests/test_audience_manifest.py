from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest

from scripts.assemble_publications import AssemblyError, Manifest, load_manifest, pages

ROOT = Path(__file__).resolve().parents[1]


class AudienceManifestSchemaTests(unittest.TestCase):
    def _create_v3_manifest(self, overrides: dict | None = None) -> dict:
        base = {
            "schema_version": 3,
            "audiences": ["use", "maintain"],
            "home": {
                "publication": "site",
                "document": "home",
            },
            "documents": [
                {
                    "publication": "site",
                    "document": "home",
                    "title": "Documentation portal",
                    "destination": "index.md",
                    "primary_audience": "use",
                    "additional_audiences": ["maintain"],
                },
                {
                    "publication": "composition",
                    "document": "getting-started",
                    "title": "Getting started",
                    "destination": "composition/getting-started.md",
                    "primary_audience": "use",
                    "additional_audiences": [],
                },
                {
                    "publication": "policy",
                    "document": "contributing",
                    "title": "Contributing",
                    "destination": "policy/contributing.md",
                    "primary_audience": "maintain",
                    "additional_audiences": [],
                },
            ],
            "navigation": {
                "use": [
                    {
                        "title": "Portal",
                        "publication": "site",
                        "document": "home",
                        "destination": "index.md",
                    },
                    {
                        "title": "Getting started",
                        "publication": "composition",
                        "document": "getting-started",
                        "destination": "composition/getting-started.md",
                    },
                ],
                "maintain": [
                    {
                        "title": "Portal",
                        "publication": "site",
                        "document": "home",
                        "destination": "index.md",
                    },
                    {
                        "title": "Contributing",
                        "publication": "policy",
                        "document": "contributing",
                        "destination": "policy/contributing.md",
                    },
                ],
            },
        }
        if overrides:
            base.update(overrides)
        return base

    def _write_manifest(self, dir_path: Path, data: dict) -> Path:
        manifest_path = dir_path / "site-manifest.json"
        manifest_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return manifest_path

    def test_production_manifest_loads_and_validates(self) -> None:
        manifest_path = ROOT / "site-manifest.json"
        manifest = load_manifest(manifest_path)
        self.assertIsInstance(manifest, Manifest)
        self.assertEqual(manifest.schema_version, 3)
        self.assertEqual(manifest.audiences, ["use", "maintain"])
        self.assertEqual(manifest.home, ("site", "portal-home"))
        self.assertEqual(manifest.document_by_key[("site", "portal-home")]["destination"], PurePosixPath("index.md"))
        self.assertGreater(len(manifest.documents), 100)

        # Unpacking compatibility: (home, projected_nav) = manifest
        home, projected_nav = manifest
        self.assertEqual(home, ("site", "portal-home"))
        self.assertIsInstance(projected_nav, list)
        self.assertIsInstance(manifest.navigation, dict)
        self.assertIn("use", manifest.navigation)
        self.assertIn("maintain", manifest.navigation)

    def test_schema_v3_loads_cleanly_with_exact_bidirectional_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_path = self._write_manifest(temp_path, self._create_v3_manifest())
            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.schema_version, 3)
            self.assertEqual(manifest.audiences, ["use", "maintain"])
            self.assertEqual(len(manifest.documents), 3)
            self.assertEqual(manifest.document_by_key[("site", "home")]["title"], "Documentation portal")
            self.assertEqual(manifest.document_by_destination[PurePosixPath("index.md")]["document"], "home")

    def test_schema_v2_backward_compatibility(self) -> None:
        v2_data = {
            "schema_version": 2,
            "home": {
                "publication": "site",
                "document": "home",
            },
            "navigation": [
                {
                    "title": "Portal",
                    "publication": "site",
                    "document": "home",
                    "destination": "index.md",
                },
                {
                    "title": "Getting started",
                    "publication": "composition",
                    "document": "getting-started",
                    "destination": "composition/getting-started.md",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_path = self._write_manifest(temp_path, v2_data)
            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.schema_version, 2)
            self.assertEqual(manifest.audiences, [])
            self.assertEqual(manifest.home, ("site", "home"))
            self.assertEqual(len(manifest.documents), 2)
            # Tuple unpacking
            home, nav = manifest
            self.assertEqual(home, ("site", "home"))
            self.assertIsInstance(nav, list)

    def test_reject_extra_root_fields(self) -> None:
        data = self._create_v3_manifest({"extra_field": "disallowed"})
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "contain exactly"):
                load_manifest(manifest_path)

    def test_reject_empty_or_invalid_audiences(self) -> None:
        for invalid_audiences in [[], ["use", "use"], ["use", ""], ["use", 123]]:
            with self.subTest(audiences=invalid_audiences):
                data = self._create_v3_manifest({"audiences": invalid_audiences})
                with tempfile.TemporaryDirectory() as temp_dir:
                    manifest_path = self._write_manifest(Path(temp_dir), data)
                    with self.assertRaisesRegex(AssemblyError, "audiences must be a non-empty array of unique strings"):
                        load_manifest(manifest_path)

    def test_reject_duplicate_document_keys(self) -> None:
        data = self._create_v3_manifest()
        data["documents"].append({
            "publication": "composition",
            "document": "getting-started",
            "title": "Duplicate Key",
            "destination": "composition/another.md",
            "primary_audience": "use",
            "additional_audiences": [],
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "duplicate document key"):
                load_manifest(manifest_path)

    def test_reject_duplicate_document_destinations(self) -> None:
        data = self._create_v3_manifest()
        data["documents"].append({
            "publication": "composition",
            "document": "unique-doc",
            "title": "Duplicate Dest",
            "destination": "composition/getting-started.md",
            "primary_audience": "use",
            "additional_audiences": [],
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "duplicate document destination"):
                load_manifest(manifest_path)

    def test_reject_non_markdown_destination(self) -> None:
        data = self._create_v3_manifest()
        data["documents"][1]["destination"] = "composition/getting-started.html"
        data["navigation"]["use"][1]["destination"] = "composition/getting-started.html"
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "must be a Markdown path"):
                load_manifest(manifest_path)

    def test_reject_undeclared_primary_audience(self) -> None:
        data = self._create_v3_manifest()
        data["documents"][1]["primary_audience"] = "developer"
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "primary_audience must be one of"):
                load_manifest(manifest_path)

    def test_reject_primary_audience_in_additional_audiences(self) -> None:
        data = self._create_v3_manifest()
        data["documents"][1]["additional_audiences"] = ["use"]
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "additional_audiences must be a list of unique audiences excluding primary_audience"):
                load_manifest(manifest_path)

    def test_reject_navigation_referencing_undeclared_document(self) -> None:
        data = self._create_v3_manifest()
        data["navigation"]["use"].append({
            "title": "Ghost",
            "publication": "policy",
            "document": "ghost-doc",
            "destination": "policy/ghost.md",
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "references undeclared document"):
                load_manifest(manifest_path)

    def test_reject_navigation_destination_mismatch(self) -> None:
        data = self._create_v3_manifest()
        data["navigation"]["use"][1]["destination"] = "composition/different.md"
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "destination mismatch"):
                load_manifest(manifest_path)

    def test_reject_document_in_navigation_without_declaring_audience(self) -> None:
        data = self._create_v3_manifest()
        # getting-started only declares 'use', try putting it in 'maintain' navigation
        data["navigation"]["maintain"].append({
            "title": "Getting started",
            "publication": "composition",
            "document": "getting-started",
            "destination": "composition/getting-started.md",
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "does not declare that audience"):
                load_manifest(manifest_path)

    def test_reject_document_declaring_audience_missing_from_navigation(self) -> None:
        data = self._create_v3_manifest()
        # Declare 'maintain' in additional_audiences for getting-started, but do not add to maintain nav
        data["documents"][1]["additional_audiences"] = ["maintain"]
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "is missing from navigation.maintain"):
                load_manifest(manifest_path)

    def test_reject_navigation_missing_audience_tree(self) -> None:
        data = self._create_v3_manifest()
        del data["navigation"]["maintain"]
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self._write_manifest(Path(temp_dir), data)
            with self.assertRaisesRegex(AssemblyError, "keys matching audiences"):
                load_manifest(manifest_path)


if __name__ == "__main__":
    unittest.main()
