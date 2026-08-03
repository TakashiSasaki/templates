from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionFinalReviewTests(unittest.TestCase):
    def copied_repository(self, destination: Path) -> Path:
        root = destination / "repository"
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "scripts", root / "scripts")
        shutil.copytree(ROOT / "docs" / "migrations", root / "docs" / "migrations")
        return root

    @staticmethod
    def contract_entry(manifest: dict[str, object], contract_id: str) -> dict[str, object]:
        return next(
            entry for entry in manifest["contracts"] if entry["id"] == contract_id
        )

    def test_cli_entry_points_reject_a_symlinked_root_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            real_parent = temporary / "real-parent"
            real_parent.mkdir()
            root = self.copied_repository(real_parent)
            alias_parent = temporary / "alias-parent"
            alias_parent.symlink_to(real_parent, target_is_directory=True)
            alias = alias_parent / root.name
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
                    "repository root path must not contain symbolic links",
                    result.stderr,
                )

    def test_manifest_migration_sequences_consumers_before_v2_publication(self) -> None:
        migration = (
            ROOT / "docs" / "migrations" / "contract-manifest-v1-to-v2.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Deployment sequencing", migration)
        self.assertIn("version 1 consumers", migration.lower())
        self.assertIn("compatibility gate", migration.lower())
        self.assertIn("before publishing", migration.lower())
        self.assertIn("version 2 manifest", migration.lower())

    def test_nul_migration_path_becomes_a_validation_diagnostic(self) -> None:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        routes = self.contract_entry(manifest, "routes")
        routes["versionHistory"][1]["migration"] = (
            "docs/migrations/routes-v1-to-v2.md\x00"
        )

        errors = validate_contract_evolution.validate_contract_evolution(
            ROOT, manifest
        )

        self.assertTrue(
            any(
                error.startswith(
                    "contract manifest routes: invalid migration path"
                )
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
