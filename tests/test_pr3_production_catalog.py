from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "catalog.json"
COMPONENT_SCHEMA = ROOT / "schemas" / "component.schema.json"
SUPPORTED_GENERATORS = {"contract-manifest-v1"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def component_path(component_id: str) -> Path:
    return ROOT / "components" / component_id / "component.json"


def recipe_path(recipe_id: str) -> Path:
    return ROOT / "recipes" / f"{recipe_id}.json"


def portable_key(path: str) -> str:
    return path.casefold()


def assert_no_portable_collisions(test: unittest.TestCase, destinations: list[str]) -> None:
    reserved = ".template-composition/lock.json"
    seen: dict[str, str] = {}
    for destination in sorted(destinations, key=lambda item: (portable_key(item), item)):
        key = portable_key(destination)
        test.assertFalse(
            key == reserved
            or key.startswith(reserved + "/")
            or reserved.startswith(key + "/"),
            f"destination structurally conflicts with reserved lock path: {destination!r}",
        )
        test.assertNotIn(
            key,
            seen,
            f"case-insensitive destination collision: {seen.get(key)!r} / {destination!r}",
        )
        seen[key] = destination
    keys = set(seen)
    for destination in destinations:
        parts = destination.split("/")
        for index in range(1, len(parts)):
            test.assertNotIn(
                "/".join(parts[:index]).casefold(),
                keys,
                f"file/directory destination collision at {destination!r}",
            )


class PR3ProductionCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load(CATALOG)
        cls.component_schema = load(COMPONENT_SCHEMA)
        cls.components = {
            component_id: load(component_path(component_id))
            for component_id in cls.catalog["components"]
        }
        cls.recipes = {
            recipe_id: load(recipe_path(recipe_id))
            for recipe_id in cls.catalog["recipes"]
        }

    def resolve(self, initial: set[str]) -> list[str]:
        resolved = set(initial)
        changed = True
        while changed:
            changed = False
            for component_id in list(resolved):
                for dependency in self.components[component_id]["requires"]:
                    if dependency not in resolved:
                        resolved.add(dependency)
                        changed = True
        for component_id in resolved:
            conflicts = set(self.components[component_id]["conflicts"])
            self.assertFalse(conflicts & resolved, f"selected conflict for {component_id}")
        return sorted(resolved)

    def render_manifest(self, selected: list[str]) -> dict:
        registrations: list[dict] = []
        for component_id in sorted(selected):
            for registration in self.components[component_id].get(
                "contract_registrations", []
            ):
                history = []
                for source_entry in registration["version_history"]:
                    entry = {
                        "version": source_entry["version"],
                        "changeType": source_entry["change_type"],
                    }
                    if "migration" in source_entry:
                        entry["migration"] = source_entry["migration"]
                    history.append(entry)
                registrations.append(
                    {
                        "id": registration["id"],
                        "document": registration["document"],
                        "schema": registration["schema"],
                        "migrationSlug": registration["migration_slug"],
                        "documentSchemaVersion": registration[
                            "document_schema_version"
                        ],
                        "versionHistory": history,
                        "purpose": registration["purpose"],
                    }
                )
        registrations.sort(key=lambda entry: entry["id"])
        return {
            "$schema": "../schemas/contract-manifest.schema.json",
            "schemaVersion": 1,
            "versionHistory": [{"version": 1, "changeType": "initial"}],
            "contracts": registrations,
            "retiredContracts": [],
        }

    def materialize(
        self,
        selected: list[str],
        target: Path,
        *,
        write_lock: bool = False,
    ) -> None:
        for component_id in selected:
            descriptor = self.components[component_id]
            component_root = component_path(component_id).parent
            for material in descriptor["materials"]:
                if "source" in material:
                    destination = target / material["destination"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(component_root / material["source"], destination)
                    continue
                generator = material["generator"]
                self.assertEqual(generator, "contract-manifest-v1")
                destination = target / material["destination"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(
                    json.dumps(self.render_manifest(selected), indent=2) + "\n",
                    encoding="utf-8",
                )
        if write_lock:
            lock_path = target / ".template-composition" / "lock.json"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(
                json.dumps(
                    {
                        "files": [{"destination": path.relative_to(target).as_posix()}
                                  for path in sorted(target.rglob("*")) if path.is_file()],
                        "resolved_components": [
                            {"id": component_id}
                            for component_id in sorted(selected)
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    def run_script(
        self,
        target: Path,
        relative: str,
        *arguments: str,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(target / relative), *arguments],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_new_descriptors_reject_symlink_sources_and_unknown_generators(self):
        validator = Draft202012Validator(self.component_schema)
        for component_id, descriptor in self.components.items():
            validator.validate(descriptor)
            component_root = component_path(component_id).parent
            actual_paths = [
                path
                for path in (component_root / "files").rglob("*")
                if path.is_file() or path.is_symlink()
            ]
            for path in actual_paths:
                self.assertFalse(
                    path.is_symlink(),
                    f"component source material must not be a symlink: "
                    f"{component_id}/{path.relative_to(component_root)}",
                )
            for material in descriptor["materials"]:
                if material["ownership"] == "generated":
                    self.assertIn(material["generator"], SUPPORTED_GENERATORS)

    def test_contract_registrations_are_globally_unique_and_owned(self):
        ids: set[str] = set()
        documents: set[str] = set()
        schemas: set[str] = set()
        for component_id, descriptor in self.components.items():
            destinations = {
                material["destination"] for material in descriptor["materials"]
            }
            for registration in descriptor.get("contract_registrations", []):
                self.assertNotIn(registration["id"], ids)
                self.assertNotIn(registration["document"], documents)
                self.assertNotIn(registration["schema"], schemas)
                ids.add(registration["id"])
                documents.add(registration["document"])
                schemas.add(registration["schema"])
                self.assertIn(registration["document"], destinations)
                self.assertIn(registration["schema"], destinations)
                versions = [
                    entry["version"]
                    for entry in registration["version_history"]
                ]
                self.assertEqual(
                    versions,
                    list(range(1, registration["document_schema_version"] + 1)),
                )
                for transition in registration["version_history"][1:]:
                    self.assertIn(transition["migration"], destinations)

    def test_contract_manifest_has_one_generated_owner(self):
        owners = []
        for component_id, descriptor in self.components.items():
            for material in descriptor["materials"]:
                if material["destination"] == "contracts/manifest.json":
                    owners.append(
                        (
                            component_id,
                            material["ownership"],
                            material.get("generator"),
                        )
                    )
        self.assertEqual(
            owners,
            [
                (
                    "lifecycle.contract-evolution",
                    "generated",
                    "contract-manifest-v1",
                )
            ],
        )

    def test_webapp_recipe_exposes_release_bundle_without_defaulting_release_chain(self):
        recipe = self.recipes["webapp"]
        self.assertEqual(recipe["artifact"], "artifact.webapp-core")
        self.assertEqual(recipe["required_components"], [])
        self.assertEqual(
            recipe["optional_components"],
            [
                "capability.cli",
                "capability.mcp",
                "capability.mcp-apps",
                "capability.pwa",
                "capability.runtime",
                "capability.service",
                "capability.web-interface",
                "lifecycle.release-bundle",
            ],
        )
        closure = self.resolve({recipe["artifact"]})
        self.assertEqual(
            closure,
            [
                "artifact.webapp-core",
                "foundation.web",
                "lifecycle.composition-state",
                "lifecycle.contract-evolution",
                "lifecycle.implementation-evidence",
                "lifecycle.lifecycle-checkpoints",
            ],
        )
        release_closure = self.resolve(
            {recipe["artifact"], "lifecycle.release-bundle"}
        )
        for component_id in (
            "lifecycle.release-execution",
            "lifecycle.release-evidence",
            "lifecycle.release-bundle",
        ):
            self.assertIn(component_id, release_closure)
        self.assertNotIn("capability.runtime", closure)

    def test_release_bundle_dependency_closure_is_artifact_neutral(self):
        self.assertEqual(
            self.resolve({"lifecycle.release-bundle"}),
            [
                "lifecycle.composition-state",
                "lifecycle.contract-evolution",
                "lifecycle.implementation-evidence",
                "lifecycle.lifecycle-checkpoints",
                "lifecycle.release-bundle",
                "lifecycle.release-evidence",
                "lifecycle.release-execution",
            ],
        )

    def test_maximal_recipe_selections_have_single_portable_owners(self):
        for recipe_id, recipe in self.recipes.items():
            selected = self.resolve(
                {
                    recipe["artifact"],
                    *recipe["required_components"],
                    *recipe["default_components"],
                    *recipe["optional_components"],
                }
            )
            destinations = [
                material["destination"]
                for component_id in selected
                for material in self.components[component_id]["materials"]
            ]
            self.assertEqual(len(destinations), len(set(destinations)), recipe_id)
            assert_no_portable_collisions(self, destinations)

    def test_generated_manifest_is_deterministic(self):
        selected = self.resolve(
            {"artifact.webapp-core", "capability.mcp-apps"}
        )
        self.assertEqual(
            self.render_manifest(selected),
            self.render_manifest(list(reversed(selected))),
        )

    def test_full_skill_lifecycle_projection_validates(self):
        recipe = self.recipes["skill"]
        selected = self.resolve(
            {recipe["artifact"], *recipe["optional_components"]}
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            self.materialize(selected, target, write_lock=True)
            skill_result = self.run_script(
                target,
                ".github/scripts/validate_skill.py",
                ".",
            )
            self.assertEqual(
                skill_result.returncode,
                0,
                skill_result.stdout + skill_result.stderr,
            )
            for script in (
                ".template-composition/validators/validate_contract_evolution.py",
                ".template-composition/validators/validate_implementation_evidence.py",
                ".template-composition/validators/validate_lifecycle_checkpoints.py",
                ".template-composition/validators/validate_release_execution.py",
                ".template-composition/validators/validate_release_evidence.py",
                ".template-composition/validators/validate_release_bundle.py",
            ):
                result = self.run_script(target, script, ".")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_minimal_webapp_template_projection_validates_without_release_materials(self):
        selected = self.resolve({"artifact.webapp-core"})
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            self.materialize(selected, target)
            scripts = (
                ("scripts/validate_contracts.py", ()),
                (
                    ".template-composition/validators/validate_contract_evolution.py",
                    (".",),
                ),
                (
                    ".template-composition/validators/validate_implementation_evidence.py",
                    (".",),
                ),
                (
                    ".template-composition/validators/validate_lifecycle_checkpoints.py",
                    (".",),
                ),
                ("scripts/validate_webapp_evidence.py", ()),
            )
            for script, arguments in scripts:
                result = self.run_script(target, script, *arguments)
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{script}\n{result.stdout}{result.stderr}",
                )
            self.assertFalse((target / "contracts/release-bundle.json").exists())

    def test_release_ready_webapp_template_projection_validates(self):
        selected = self.resolve(
            {"artifact.webapp-core", "lifecycle.release-bundle"}
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            self.materialize(selected, target)
            for script in (
                ".template-composition/validators/validate_release_execution.py",
                ".template-composition/validators/validate_release_evidence.py",
                ".template-composition/validators/validate_release_bundle.py",
            ):
                result = self.run_script(target, script, ".")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_minimal_webapp_manifest_preserves_domain_versions(self):
        selected = self.resolve({"artifact.webapp-core"})
        entries = {
            entry["id"]: entry
            for entry in self.render_manifest(selected)["contracts"]
        }
        self.assertEqual(
            set(entries),
            {
                "application_routes",
                "browser_identity",
                "implementation_evidence",
                "lifecycle_checkpoints",
                "routes",
                "surfaces",
                "ui_states",
                "viewports",
            },
        )
        self.assertEqual(entries["application_routes"]["documentSchemaVersion"], 1)
        self.assertEqual(entries["routes"]["documentSchemaVersion"], 5)
        self.assertEqual(entries["ui_states"]["documentSchemaVersion"], 2)
        self.assertEqual(
            [entry["version"] for entry in entries["routes"]["versionHistory"]],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(
            [entry["version"] for entry in entries["ui_states"]["versionHistory"]],
            [1, 2],
        )

    def test_release_ready_webapp_manifest_adds_release_contracts(self):
        selected = self.resolve(
            {"artifact.webapp-core", "lifecycle.release-bundle"}
        )
        entries = {
            entry["id"]: entry
            for entry in self.render_manifest(selected)["contracts"]
        }
        self.assertTrue(
            {"release_execution", "release_evidence", "release_bundle"} <= set(entries)
        )
        self.assertEqual(entries["release_execution"]["documentSchemaVersion"], 2)


if __name__ == "__main__":
    unittest.main()
