from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class ContractManifestTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        temporary_root = Path(temporary_directory)
        shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
        shutil.copytree(ROOT / "schemas", temporary_root / "schemas")
        return temporary_root

    @staticmethod
    def write_manifest(root: Path, manifest: dict[str, object]) -> None:
        (root / validate_contracts.MANIFEST_PATH).write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_registry_is_loaded_from_the_contract_manifest(self) -> None:
        self.assertEqual(
            {
                "surfaces": (
                    "contracts/surfaces.json",
                    "schemas/surfaces.schema.json",
                ),
                "routes": (
                    "contracts/routes.json",
                    "schemas/routes.schema.json",
                ),
                "ui_states": (
                    "contracts/ui-states.json",
                    "schemas/ui-states.schema.json",
                ),
                "viewports": (
                    "contracts/viewports.json",
                    "schemas/viewports.schema.json",
                ),
            },
            validate_contracts.CONTRACT_SCHEMAS,
        )
        self.assertEqual(
            validate_contracts.CONTRACT_SCHEMAS,
            validate_contracts.load_contract_registry(ROOT),
        )


    def test_missing_manifest_is_reported_without_import_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            shutil.copytree(ROOT / "scripts", root / "scripts")
            (root / validate_contracts.MANIFEST_PATH).unlink()
            module_path = root / "scripts/validate_contracts.py"
            spec = importlib.util.spec_from_file_location(
                "validate_contracts_missing_manifest", module_path
            )
            self.assertIsNotNone(spec)
            assert spec is not None
            self.assertIsNotNone(spec.loader)
            assert spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self.assertEqual({}, module.CONTRACT_SCHEMAS)
            errors = module.validate_repository(root)

        self.assertTrue(
            any(
                error.startswith("contracts/manifest.json: unable to load JSON:")
                for error in errors
            )
        )

    def test_unregistered_contract_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "contracts/unregistered.json").write_text("{}\n", encoding="utf-8")
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "unregistered contract document: contracts/unregistered.json",
            errors,
        )

    def test_unregistered_contract_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "schemas/unregistered.schema.json").write_text(
                '{"$schema":"https://json-schema.org/draft/2020-12/schema"}\n',
                encoding="utf-8",
            )
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "unregistered contract schema: schemas/unregistered.schema.json",
            errors,
        )

    def test_missing_registered_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "contracts/routes.json").unlink()
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contract manifest routes: missing document: contracts/routes.json",
            errors,
        )

    def test_duplicate_manifest_identifiers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][1]["id"] = manifest["contracts"][0]["id"]
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertIn("duplicate contract id: surfaces", errors)

    def test_manifest_path_escape_is_rejected_before_file_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][0]["document"] = "../outside.json"
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any(
                error.startswith(
                    "contracts/manifest.json:$.contracts[0].document:"
                )
                for error in errors
            )
        )

    def test_document_schema_version_must_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][1]["documentSchemaVersion"] = 2
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contracts/routes.json: schemaVersion does not match manifest: "
            "expected 2, got 1",
            errors,
        )

    def test_manifest_purpose_requires_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][0]["purpose"] = "\u2800"
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contract manifest surfaces: purpose must contain at least one visible character",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
