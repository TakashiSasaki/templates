from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionSecondReviewTests(unittest.TestCase):
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

    def test_bootstrap_migration_slug_is_reserved_for_active_contracts(self) -> None:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        surfaces = self.contract_entry(manifest, "surfaces")
        surfaces["migrationSlug"] = "contract-manifest"

        errors = validate_contract_evolution.validate_contract_evolution(
            ROOT, manifest
        )

        self.assertIn(
            "contract manifest surfaces: migrationSlug contract-manifest is reserved for the manifest bootstrap",
            errors,
        )

    def test_bootstrap_migration_slug_is_reserved_for_retired_contracts(self) -> None:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        retired = self.retired_contract()
        retired["migrationSlug"] = "contract-manifest"
        manifest["retiredContracts"].append(retired)

        errors = validate_contract_evolution.validate_contract_evolution(
            ROOT, manifest
        )

        self.assertIn(
            "retired contract manifest legacy: migrationSlug contract-manifest is reserved for the manifest bootstrap",
            errors,
        )

    def test_non_object_retirement_history_entry_becomes_diagnostic(self) -> None:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        retired = self.retired_contract()
        retired["versionHistory"][-1] = "not-an-object"
        manifest["retiredContracts"].append(retired)

        errors = validate_contract_evolution.validate_contract_evolution(
            ROOT, manifest
        )

        self.assertTrue(
            any(
                error.startswith(
                    "contracts/manifest.json: evolution metadata is incomplete or malformed:"
                )
                for error in errors
            ),
            errors,
        )

    def test_registered_domain_migrations_cover_required_operational_topics(self) -> None:
        required_sections = (
            "## Compatibility impact",
            "## Identifier mappings",
            "## Implementation and evidence",
            "## Deployment sequencing",
            "## Rollback",
        )

        for filename in ("routes-v1-to-v2.md", "ui-states-v1-to-v2.md"):
            migration = (ROOT / "docs" / "migrations" / filename).read_text(
                encoding="utf-8"
            )
            with self.subTest(filename=filename):
                for section in required_sections:
                    self.assertIn(section, migration)

    def test_retired_purpose_requires_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            manifest = copy.deepcopy(validate_contracts.load_contract_manifest(root))
            retired = self.retired_contract()
            retired["purpose"] = "\u2800"
            manifest["retiredContracts"].append(retired)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "retired contract manifest legacy: purpose must contain at least one visible character",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
