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


class ContractManifestReviewRegressionTests(unittest.TestCase):
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

    def test_core_contract_id_is_bound_to_canonical_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = validate_contracts.load_contract_manifest(root)
            manifest["contracts"][0]["id"], manifest["contracts"][1]["id"] = (
                manifest["contracts"][1]["id"],
                manifest["contracts"][0]["id"],
            )
            self.write_manifest(root, manifest)
            errors = validate_contracts.validate_repository(root)

        self.assertTrue(
            any(
                error.startswith("contracts/manifest.json:$.contracts:")
                and "does not contain items matching the given schema" in error
                for error in errors
            ),
            errors,
        )

    def test_every_json_file_in_schema_directory_must_be_registered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            (root / "schemas/shared.json").write_text(
                '{"$schema":"https://json-schema.org/draft/2020-12/schema"}\n',
                encoding="utf-8",
            )
            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "unregistered contract schema: schemas/shared.json",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
