from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class ContractManifestSecurityRegressionTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        root = Path(temporary_directory)
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        return root

    @staticmethod
    def write_manifest(root: Path, manifest: dict[str, object]) -> None:
        (root / validate_contracts.MANIFEST_PATH).write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_symlinked_bootstrap_schema_is_rejected_before_reading_external_content(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            schema_path = root / validate_contracts.MANIFEST_SCHEMA_PATH
            external_schema = (
                root.parent / f"{root.name}-external-contract-manifest.schema.json"
            )
            external_schema.write_text(
                schema_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            schema_path.unlink()
            schema_path.symlink_to(external_schema)
            try:
                errors = validate_contracts.validate_repository(root)
            finally:
                external_schema.unlink(missing_ok=True)

        self.assertIn(
            "schemas/contract-manifest.schema.json: bootstrap schema must not be "
            "a symbolic link",
            errors,
        )

    def test_symlinked_inventory_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            external_directory = root.parent / f"{root.name}-external-schemas"
            external_directory.mkdir()
            (external_directory / "types.json").write_text("{}\n", encoding="utf-8")
            linked_directory = root / "schemas/shared"
            linked_directory.symlink_to(external_directory, target_is_directory=True)
            try:
                errors = validate_contracts.validate_repository(root)
            finally:
                shutil.rmtree(external_directory, ignore_errors=True)

        self.assertIn(
            "schemas/shared: repository-owned directory must not be a symbolic link",
            errors,
        )

    def test_nested_json_schema_file_must_be_registered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            nested_directory = root / "schemas/shared"
            nested_directory.mkdir()
            (nested_directory / "types.json").write_text(
                '{"$schema":"https://json-schema.org/draft/2020-12/schema"}\n',
                encoding="utf-8",
            )
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "unregistered contract schema: schemas/shared/types.json",
            errors,
        )

    def test_registered_document_must_be_an_object_with_version_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            document_path = root / "contracts/list.json"
            schema_path = root / "schemas/list.schema.json"
            document_path.write_text('["value"]\n', encoding="utf-8")
            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"].append(
                {
                    "id": "list",
                    "document": "contracts/list.json",
                    "schema": "schemas/list.schema.json",
                    "documentSchemaVersion": 1,
                    "purpose": "Exercise metadata enforcement for future contracts.",
                }
            )
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contracts/list.json: registered contract document must be a JSON object "
            "with $schema and schemaVersion metadata",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
