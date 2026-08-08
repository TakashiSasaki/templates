from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionCodexRegressionTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        root = Path(temporary_directory) / "repository"
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "docs" / "migrations", root / "docs" / "migrations")
        return root

    @staticmethod
    def contract_entry(manifest: dict[str, object], contract_id: str) -> dict[str, object]:
        return next(
            entry for entry in manifest["contracts"] if entry["id"] == contract_id
        )

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
            "# Retire legacy contract\n\n## Rollback\nRestore the version 1 files.\n",
            encoding="utf-8",
        )

    def test_alternate_extension_migration_artifacts_are_not_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            migrations = root / "docs" / "migrations"
            (migrations / "stale.MD").write_text("# Stale\n", encoding="utf-8")
            (migrations / "stale.markdown").write_text(
                "# Stale\n", encoding="utf-8"
            )
            manifest = validate_contracts.load_contract_manifest(root)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "unregistered migration document: docs/migrations/stale.MD",
            errors,
        )
        self.assertIn(
            "unregistered migration document: docs/migrations/stale.markdown",
            errors,
        )

    def test_manifest_migration_documents_concrete_rollback_implications(self) -> None:
        migration = (
            ROOT / "docs" / "migrations" / "contract-manifest-v1-to-v2.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Rollback", migration)
        self.assertIn("restore", migration.lower())
        self.assertIn("version 1", migration.lower())
        self.assertIn("forward-fix", migration.lower())

    def test_historical_migration_slug_survives_document_path_rename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            routes = self.contract_entry(manifest, "routes")
            self.assertEqual("routes", routes["migrationSlug"])
            routes["document"] = "contracts/renamed-routes.json"

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertFalse(
            any(
                "renamed-routes-v1-to-v2.md" in error
                for error in errors
            ),
            errors,
        )
        self.assertFalse(
            any(
                error.startswith("contract manifest routes: version 2 migration must be")
                for error in errors
            ),
            errors,
        )

    def test_retired_contract_tombstone_preserves_history_without_live_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.create_retirement_migration(root)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            manifest["retiredContracts"].append(self.retired_contract())
            schema = validate_contracts.load_json(
                root / validate_contracts.MANIFEST_SCHEMA_PATH
            )

            self.assertTrue(Draft202012Validator(schema).is_valid(manifest))
            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertEqual([], errors)

    def test_retired_version_follows_last_live_document_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.create_retirement_migration(root)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            retired = self.retired_contract()
            retired["retiredVersion"] = 3
            manifest["retiredContracts"].append(retired)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "retired contract manifest legacy: retiredVersion must equal lastDocumentSchemaVersion plus 1",
            errors,
        )

    def test_retirement_transition_must_be_breaking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.create_retirement_migration(root)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            retired = self.retired_contract()
            retired["versionHistory"][-1]["changeType"] = "additive"
            manifest["retiredContracts"].append(retired)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "retired contract manifest legacy: retirement transition must be breaking",
            errors,
        )

    def test_active_and_retired_contracts_must_not_share_migration_slug(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.create_retirement_migration(root)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            retired = self.retired_contract()
            retired["migrationSlug"] = "routes"
            retired["versionHistory"][-1]["migration"] = (
                "docs/migrations/routes-v1-to-v2.md"
            )
            manifest["retiredContracts"].append(retired)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "duplicate active or retired migration slug: routes",
            errors,
        )

    def test_manifest_preflight_runtime_error_becomes_diagnostic(self) -> None:
        with patch.object(
            validate_contract_evolution.validate_contracts,
            "load_contract_manifest",
            side_effect=RuntimeError("unsafe manifest preflight"),
        ):
            errors = validate_contract_evolution.validate_contract_evolution(ROOT)

        self.assertEqual(
            [
                "contracts/manifest.json: unable to load JSON: unsafe manifest preflight"
            ],
            errors,
        )

    def test_huge_current_version_is_rejected_without_materializing_range(self) -> None:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        routes = self.contract_entry(manifest, "routes")
        huge_version = 10**100
        routes["documentSchemaVersion"] = huge_version

        errors = validate_contract_evolution.validate_contract_evolution(
            ROOT, manifest
        )

        self.assertIn(
            "contract manifest routes: versionHistory must contain contiguous versions "
            f"1 through {huge_version}",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
