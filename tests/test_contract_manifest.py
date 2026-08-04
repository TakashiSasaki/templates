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
                "release_bundle": (
                    "contracts/release-bundle.json",
                    "schemas/release-bundle.schema.json",
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

        self.assertTrue(
            any(
                error.startswith("contracts/manifest.json:$.contracts:")
                and "does not contain items matching the given schema" in error
                for error in errors
            ),
            errors,
        )

    def test_self_referential_registered_symlink_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            target = root / "contracts/surfaces.json"
            target.unlink()
            target.symlink_to(target.name)
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contract manifest surfaces: document must not be a symbolic link: "
            "contracts/surfaces.json",
            errors,
        )

    def test_symlinked_manifest_is_rejected_before_reading_external_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest_path = root / validate_contracts.MANIFEST_PATH
            external_manifest = root.parent / f"{root.name}-external-manifest.json"
            external_manifest.write_text(
                manifest_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            manifest_path.unlink()
            manifest_path.symlink_to(external_manifest)
            try:
                errors = validate_contracts.validate_repository(root)
            finally:
                external_manifest.unlink(missing_ok=True)

        self.assertIn(
            "contracts/manifest.json: manifest must not be a symbolic link",
            errors,
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
            manifest["contracts"].append(dict(manifest["contracts"][0]))
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
            manifest["contracts"][1]["documentSchemaVersion"] = 3
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contracts/routes.json: schemaVersion does not match manifest: "
            "expected 3, got 2",
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
