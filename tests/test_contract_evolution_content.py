from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionContentTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        root = Path(temporary_directory) / "repository"
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "docs" / "migrations", root / "docs" / "migrations")
        return root

    def test_visually_empty_migration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            migration = root / "docs" / "migrations" / "routes-v1-to-v2.md"
            migration.write_text("\u2800\n", encoding="utf-8")
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "contract manifest routes: migration must contain at least one visible character: docs/migrations/routes-v1-to-v2.md",
            errors,
        )

    def test_invalid_utf8_migration_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            migration = root / "docs" / "migrations" / "routes-v1-to-v2.md"
            migration.write_bytes(b"\xff")
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertTrue(
            any(
                error.startswith(
                    "contract manifest routes: unable to read migration docs/migrations/routes-v1-to-v2.md:"
                )
                for error in errors
            )
        )

    def test_repository_root_must_not_be_a_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            alias = Path(temporary_directory) / "repository-link"
            alias.symlink_to(root.name, target_is_directory=True)
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                alias, manifest
            )

        self.assertEqual(
            ["repository root must not be a symbolic link"],
            errors,
        )


if __name__ == "__main__":
    unittest.main()
