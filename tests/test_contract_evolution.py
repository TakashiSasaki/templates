from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contract_evolution  # noqa: E402
import validate_contracts  # noqa: E402


class ContractEvolutionTests(unittest.TestCase):
    def copied_repository(self, temporary_directory: str) -> Path:
        root = Path(temporary_directory)
        shutil.copytree(ROOT / "contracts", root / "contracts")
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "docs" / "migrations", root / "docs" / "migrations")
        return root

    @staticmethod
    def write_manifest(root: Path, manifest: dict[str, object]) -> None:
        (root / validate_contracts.MANIFEST_PATH).write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def evolved_manifest() -> dict[str, object]:
        manifest = copy.deepcopy(validate_contracts.load_contract_manifest(ROOT))
        manifest["schemaVersion"] = 2
        manifest["versionHistory"] = [
            {"version": 1, "changeType": "initial"},
            {
                "version": 2,
                "changeType": "breaking",
                "migration": "docs/migrations/contract-manifest-v1-to-v2.md",
            },
        ]
        histories = {
            "surfaces": [{"version": 1, "changeType": "initial"}],
            "routes": [
                {"version": 1, "changeType": "initial"},
                {
                    "version": 2,
                    "changeType": "breaking",
                    "migration": "docs/migrations/routes-v1-to-v2.md",
                },
            ],
            "ui_states": [
                {"version": 1, "changeType": "initial"},
                {
                    "version": 2,
                    "changeType": "breaking",
                    "migration": "docs/migrations/ui-states-v1-to-v2.md",
                },
            ],
            "viewports": [{"version": 1, "changeType": "initial"}],
            "implementation_evidence": [
                {"version": 1, "changeType": "initial"}
            ],
            "release_evidence": [
                {"version": 1, "changeType": "initial"}
            ],
            "release_bundle": [
                {"version": 1, "changeType": "initial"}
            ],
        }
        for entry in manifest["contracts"]:
            entry["versionHistory"] = histories[entry["id"]]
        return manifest

    @staticmethod
    def contract_entry(manifest: dict[str, object], contract_id: str) -> dict[str, object]:
        return next(
            entry for entry in manifest["contracts"] if entry["id"] == contract_id
        )

    @staticmethod
    def ensure_manifest_migration(root: Path) -> None:
        path = root / "docs" / "migrations" / "contract-manifest-v1-to-v2.md"
        path.write_text("# Contract manifest schema version 1 to 2\n", encoding="utf-8")

    def test_repository_records_complete_version_histories(self) -> None:
        manifest = validate_contracts.load_contract_manifest(ROOT)

        self.assertEqual(2, manifest["schemaVersion"])
        self.assertEqual(
            self.evolved_manifest()["versionHistory"], manifest["versionHistory"]
        )
        expected = {
            entry["id"]: entry["versionHistory"]
            for entry in self.evolved_manifest()["contracts"]
        }
        actual = {
            entry["id"]: entry["versionHistory"]
            for entry in manifest["contracts"]
        }
        self.assertEqual(expected, actual)

    def test_manifest_schema_accepts_required_evolution_metadata(self) -> None:
        schema = validate_contracts.load_json(
            ROOT / validate_contracts.MANIFEST_SCHEMA_PATH
        )
        validator = Draft202012Validator(schema)
        manifest = self.evolved_manifest()

        self.assertTrue(validator.is_valid(manifest))

        del manifest["versionHistory"]
        self.assertFalse(validator.is_valid(manifest))

    def test_history_versions_must_be_contiguous_and_end_at_current_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.ensure_manifest_migration(root)
            manifest = self.evolved_manifest()
            routes = self.contract_entry(manifest, "routes")
            routes["versionHistory"] = [
                {"version": 1, "changeType": "initial"},
                {
                    "version": 3,
                    "changeType": "breaking",
                    "migration": "docs/migrations/routes-v2-to-v3.md",
                },
            ]
            self.write_manifest(root, manifest)

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "contract manifest routes: versionHistory must contain contiguous versions 1 through 2",
            errors,
        )

    def test_migration_path_must_match_contract_and_transition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.ensure_manifest_migration(root)
            manifest = self.evolved_manifest()
            routes = self.contract_entry(manifest, "routes")
            routes["versionHistory"][1]["migration"] = (
                "docs/migrations/ui-states-v1-to-v2.md"
            )

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "contract manifest routes: version 2 migration must be docs/migrations/routes-v1-to-v2.md",
            errors,
        )

    def test_missing_registered_migration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.ensure_manifest_migration(root)
            manifest = self.evolved_manifest()
            (root / "docs" / "migrations" / "routes-v1-to-v2.md").unlink()

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "contract manifest routes: missing migration: docs/migrations/routes-v1-to-v2.md",
            errors,
        )

    def test_symlinked_registered_migration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.ensure_manifest_migration(root)
            manifest = self.evolved_manifest()
            migration = root / "docs" / "migrations" / "routes-v1-to-v2.md"
            migration.unlink()
            migration.symlink_to("ui-states-v1-to-v2.md")

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "contract manifest routes: migration must not be a symbolic link: docs/migrations/routes-v1-to-v2.md",
            errors,
        )

    def test_unregistered_migration_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.ensure_manifest_migration(root)
            manifest = self.evolved_manifest()
            extra = root / "docs" / "migrations" / "unused-v1-to-v2.md"
            extra.write_text("# Unused migration\n", encoding="utf-8")

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "unregistered migration document: docs/migrations/unused-v1-to-v2.md",
            errors,
        )

    def test_duplicate_migration_registration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self.copied_repository(temporary_directory)
            self.ensure_manifest_migration(root)
            manifest = self.evolved_manifest()
            ui_states = self.contract_entry(manifest, "ui_states")
            ui_states["versionHistory"][1]["migration"] = (
                "docs/migrations/routes-v1-to-v2.md"
            )

            errors = validate_contract_evolution.validate_contract_evolution(
                root, manifest
            )

        self.assertIn(
            "duplicate migration document: docs/migrations/routes-v1-to-v2.md",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
