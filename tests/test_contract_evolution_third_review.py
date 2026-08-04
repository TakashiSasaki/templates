from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionThirdReviewTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        root = Path(temporary_directory) / "repository"
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "scripts", root / "scripts")
        shutil.copytree(ROOT / "docs" / "migrations", root / "docs" / "migrations")
        return root

    @staticmethod
    def retired_contract() -> dict[str, object]:
        return {
            "id": "legacy",
            "document": "contracts/legacy.json",
            "schema": "schemas/legacy.schema.json",
            "migrationSlug": "legacy",
            "lastDocumentSchemaVersion": 1,
            "retiredVersion": 2,
            "versionHistory": [
                {"version": 1, "changeType": "initial"},
                {
                    "version": 2,
                    "changeType": "breaking",
                    "migration": "docs/migrations/legacy-v1-to-v2.md",
                },
            ],
            "purpose": "Preserve the retired legacy contract history.",
        }

    @staticmethod
    def create_retirement_migration(root: Path) -> None:
        migration = root / "docs" / "migrations" / "legacy-v1-to-v2.md"
        migration.write_text(
            "# Retire legacy contract\n\n## Rollback\nRestore version 1.\n",
            encoding="utf-8",
        )

    def test_migration_directory_ancestors_must_not_be_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            external_docs = Path(temporary_directory) / "external-docs"
            (root / "docs").rename(external_docs)
            (external_docs / "migrations" / "external-secret.txt").write_text(
                "secret\n", encoding="utf-8"
            )
            (root / "docs").symlink_to(external_docs, target_is_directory=True)
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertEqual(
            ["docs/migrations: migration path must not contain symbolic links"],
            errors,
        )
        self.assertFalse(any("external-secret" in error for error in errors))

    def test_cli_entry_points_preserve_a_symlinked_invocation_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            alias = Path(temporary_directory) / "repository-link"
            alias.symlink_to(root.name, target_is_directory=True)
            environment = os.environ.copy()
            environment["PWD"] = str(alias)

            direct = subprocess.run(
                [
                    sys.executable,
                    str(alias / "scripts" / "validate_contract_evolution.py"),
                ],
                cwd=alias,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            module = subprocess.run(
                [sys.executable, "-m", "scripts.validate_contract_evolution"],
                cwd=alias,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        for result in (direct, module):
            with self.subTest(command=result.args):
                self.assertEqual(1, result.returncode)
                self.assertIn(
                    "repository root must not be a symbolic link",
                    result.stderr,
                )

    def test_retired_contracts_must_not_claim_bootstrap_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.create_retirement_migration(root)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            retired = self.retired_contract()
            retired["document"] = validate_contracts.MANIFEST_PATH
            retired["schema"] = validate_contracts.MANIFEST_SCHEMA_PATH
            manifest["retiredContracts"].append(retired)
            schema = validate_contracts.load_json(
                root / validate_contracts.MANIFEST_SCHEMA_PATH
            )

            self.assertFalse(Draft202012Validator(schema).is_valid(manifest))
            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "retired contract manifest legacy: document must not claim bootstrap path contracts/manifest.json",
            errors,
        )
        self.assertIn(
            "retired contract manifest legacy: schema must not claim bootstrap path schemas/contract-manifest.schema.json",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
