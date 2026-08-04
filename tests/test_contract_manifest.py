from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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
                "implementation_evidence": (
                    "contracts/implementation-evidence.json",
                    "schemas/implementation-evidence.schema.json",
                ),
                "release_evidence": (
                    "contracts/release-evidence.json",
                    "schemas/release-evidence.schema.json",
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
            result = subprocess.run(
                [sys.executable, str(root / "scripts/validate_contracts.py")],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "contracts/manifest.json: unable to load JSON:",
            result.stderr,
        )

    def test_missing_core_contract_role_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"] = [
                entry for entry in manifest["contracts"] if entry["id"] != "viewports"
            ]
            self.write_manifest(root, manifest)
            (root / "contracts/viewports.json").unlink()
            (root / "schemas/viewports.schema.json").unlink()

            errors = validate_contracts.validate_repository(root)

        self.assertIn("contract manifest: missing core contract id: viewports", errors)

    def test_duplicate_manifest_identifiers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            duplicate = dict(manifest["contracts"][0])
            duplicate["document"] = "contracts/duplicate.json"
            duplicate["schema"] = "schemas/duplicate.schema.json"
            manifest["contracts"].append(duplicate)
            self.write_manifest(root, manifest)

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any(error.startswith("contract manifest: duplicate contract id:") for error in errors),
            errors,
        )

    def test_missing_registered_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "contracts/routes.json").unlink()

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any("contract document not found" in error for error in errors),
            errors,
        )

    def test_document_schema_version_must_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            route_path = root / "contracts/routes.json"
            routes = validate_contracts.load_json(route_path)
            routes["schemaVersion"] = 1
            route_path.write_text(json.dumps(routes, indent=2) + "\n", encoding="utf-8")

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any("schemaVersion does not match manifest" in error for error in errors),
            errors,
        )

    def test_unregistered_contract_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "contracts/extra.json").write_text("{}\n", encoding="utf-8")

            errors = validate_contracts.validate_repository(root)

        self.assertIn("unregistered contract document: contracts/extra.json", errors)

    def test_unregistered_contract_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "schemas/extra.schema.json").write_text("{}\n", encoding="utf-8")

            errors = validate_contracts.validate_repository(root)

        self.assertIn("unregistered contract schema: schemas/extra.schema.json", errors)

    def test_manifest_path_escape_is_rejected_before_file_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][0]["document"] = "../outside.json"
            self.write_manifest(root, manifest)

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any("path must stay within the repository" in error for error in errors),
            errors,
        )

    def test_manifest_purpose_requires_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][0]["purpose"] = " \n\t"
            self.write_manifest(root, manifest)

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any("purpose must contain visible text" in error for error in errors),
            errors,
        )

    def test_symlinked_manifest_is_rejected_before_reading_external_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            external = Path(temporary_directory) / "outside.json"
            external.write_text("{}\n", encoding="utf-8")
            manifest_path = root / validate_contracts.MANIFEST_PATH
            manifest_path.unlink()
            manifest_path.symlink_to(external)

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any("manifest must not be a symbolic link" in error for error in errors),
            errors,
        )

    def test_self_referential_registered_symlink_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            route_path = root / "contracts/routes.json"
            route_path.unlink()
            route_path.symlink_to("routes.json")

            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any("must not be a symbolic link" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
