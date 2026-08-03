from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionSecurityTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        root = Path(temporary_directory)
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "docs" / "migrations", root / "docs" / "migrations")
        return root

    def test_incomplete_evolution_metadata_is_reported_without_crashing(self) -> None:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        del manifest["versionHistory"]

        errors = validate_contract_evolution.validate_contract_evolution(
            ROOT, manifest
        )

        self.assertEqual(1, len(errors))
        self.assertTrue(
            errors[0].startswith(
                "contracts/manifest.json: evolution metadata is incomplete or malformed:"
            )
        )

    def test_migration_root_must_not_be_a_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            migrations = root / "docs" / "migrations"
            target = root / "docs" / "migration-target"
            migrations.rename(target)
            migrations.symlink_to(target.name, target_is_directory=True)
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertEqual(
            ["docs/migrations: migration directory must not be a symbolic link"],
            errors,
        )

    def test_nested_migration_directory_must_not_be_a_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            migrations = root / "docs" / "migrations"
            target = migrations / "nested-target"
            target.mkdir()
            (migrations / "nested-link").symlink_to(
                target.name, target_is_directory=True
            )
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "docs/migrations/nested-link: migration directory must not be a symbolic link",
            errors,
        )

    def test_registered_migration_must_be_a_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            migration = root / "docs" / "migrations" / "routes-v1-to-v2.md"
            migration.unlink()
            migration.mkdir()
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "contract manifest routes: migration must be a regular file: docs/migrations/routes-v1-to-v2.md",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
