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
RECIPE_SCHEMA = ROOT / "schemas" / "recipe.schema.json"
CATALOG_SCHEMA = ROOT / "schemas" / "catalog.schema.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def component_path(component_id: str) -> Path:
    return ROOT / "components" / component_id / "component.json"


def recipe_path(recipe_id: str) -> Path:
    return ROOT / "recipes" / f"{recipe_id}.json"


def portable_key(path: str) -> str:
    return path.casefold()


def assert_no_portable_collisions(test: unittest.TestCase, destinations: list[str]) -> None:
    ordered = sorted(destinations, key=lambda item: (portable_key(item), item))
    seen: dict[str, str] = {}
    reserved_lock = ".template-composition/lock.json"
    for destination in ordered:
        key = portable_key(destination)
        test.assertFalse(
            key == reserved_lock
            or key.startswith(reserved_lock + "/")
            or reserved_lock.startswith(key + "/"),
            f"destination structurally conflicts with reserved lock path: {destination!r}",
        )
        test.assertNotIn(key, seen, f"case-insensitive destination collision: {seen.get(key)!r} / {destination!r}")
        seen[key] = destination
    keys = set(seen)
    for destination in destinations:
        parts = destination.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index]).casefold()
            test.assertNotIn(parent, keys, f"file/directory destination collision at {destination!r}")


class ProductionCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load(CATALOG)
        cls.component_schema = load(COMPONENT_SCHEMA)
        cls.recipe_schema = load(RECIPE_SCHEMA)
        cls.catalog_schema = load(CATALOG_SCHEMA)
        cls.components = {
            component_id: load(component_path(component_id))
            for component_id in cls.catalog["components"]
        }
        cls.recipes = {
            recipe_id: load(recipe_path(recipe_id))
            for recipe_id in cls.catalog["recipes"]
        }

    def test_catalog_schema_and_document_are_valid(self):
        Draft202012Validator.check_schema(self.catalog_schema)
        Draft202012Validator(self.catalog_schema).validate(self.catalog)

    def test_catalog_is_closed_and_lexically_ordered(self):
        self.assertEqual(self.catalog["components"], sorted(self.catalog["components"]))
        self.assertEqual(self.catalog["recipes"], sorted(self.catalog["recipes"]))
        component_dirs = sorted(
            path.name for path in (ROOT / "components").iterdir()
            if path.is_dir()
        )
        recipe_ids = sorted(path.stem for path in (ROOT / "recipes").glob("*.json"))
        self.assertEqual(component_dirs, self.catalog["components"])
        self.assertEqual(recipe_ids, self.catalog["recipes"])

    def test_component_descriptors_and_sources_are_closed(self):
        validator = Draft202012Validator(self.component_schema)
        component_ids = set(self.components)
        for component_id, descriptor in self.components.items():
            with self.subTest(component=component_id):
                validator.validate(descriptor)
                self.assertEqual(descriptor["id"], component_id)
                self.assertEqual(descriptor["kind"], component_id.split(".", 1)[0])
                self.assertNotIn(component_id, descriptor["requires"])
                self.assertFalse(set(descriptor["requires"]) & set(descriptor["conflicts"]))
                for referenced in descriptor["requires"] + descriptor["conflicts"]:
                    self.assertIn(referenced, component_ids)
                if descriptor["kind"] in {"capability", "lifecycle"}:
                    self.assertFalse(
                        any(item.startswith("artifact.") for item in descriptor["requires"] + descriptor["conflicts"])
                    )

                component_root = component_path(component_id).parent
                declared = sorted(
                    material["source"]
                    for material in descriptor["materials"]
                    if "source" in material
                )
                actual = sorted(
                    path.relative_to(component_root).as_posix()
                    for path in (component_root / "files").rglob("*")
                    if path.is_file()
                )
                self.assertEqual(actual, declared)
                for source in declared:
                    self.assertTrue((component_root / source).is_file())

    def test_dependency_graph_is_acyclic(self):
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(component_id: str) -> None:
            if component_id in visited:
                return
            self.assertNotIn(component_id, visiting, f"dependency cycle at {component_id}")
            visiting.add(component_id)
            for dependency in self.components[component_id]["requires"]:
                visit(dependency)
            visiting.remove(component_id)
            visited.add(component_id)

        for component_id in self.catalog["components"]:
            visit(component_id)

    def test_recipes_reference_the_closed_catalog(self):
        validator = Draft202012Validator(self.recipe_schema)
        for recipe_id, recipe in self.recipes.items():
            with self.subTest(recipe=recipe_id):
                validator.validate(recipe)
                self.assertEqual(recipe["id"], recipe_id)
                self.assertIn(recipe["artifact"], self.components)
                self.assertEqual(self.components[recipe["artifact"]]["kind"], "artifact")
                groups = [
                    set(recipe["required_components"]),
                    set(recipe["default_components"]),
                    set(recipe["optional_components"]),
                ]
                self.assertFalse(groups[0] & groups[1])
                self.assertFalse(groups[0] & groups[2])
                self.assertFalse(groups[1] & groups[2])
                for component_id in set().union(*groups):
                    self.assertIn(component_id, self.components)
                    self.assertNotEqual(self.components[component_id]["kind"], "artifact")

    def test_skill_recipe_exposes_generic_capabilities_and_lifecycle(self):
        recipe = self.recipes["skill"]
        self.assertEqual(recipe["artifact"], "artifact.skill-core")
        self.assertEqual(recipe["required_components"], [])
        self.assertEqual(recipe["default_components"], [])
        self.assertEqual(
            recipe["optional_components"],
            [
                "capability.cli",
                "capability.mcp",
                "capability.mcp-apps",
                "capability.runtime",
                "capability.service",
                "capability.web-interface",
                "lifecycle.contract-evolution",
                "lifecycle.implementation-evidence",
                "lifecycle.release-bundle",
                "lifecycle.release-evidence",
                "lifecycle.release-execution",
            ],
        )

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

    def test_capability_dependency_closure(self):
        self.assertEqual(
            self.resolve({"capability.mcp-apps"}),
            [
                "capability.mcp",
                "capability.mcp-apps",
                "capability.runtime",
                "lifecycle.composition-state",
                "lifecycle.contract-evolution",
                "lifecycle.implementation-evidence",
                "lifecycle.lifecycle-checkpoints",
            ],
        )
        self.assertEqual(
            self.resolve({"capability.cli"}),
            [
                "capability.cli",
                "capability.runtime",
                "lifecycle.composition-state",
                "lifecycle.contract-evolution",
                "lifecycle.implementation-evidence",
                "lifecycle.lifecycle-checkpoints",
            ],
        )
        self.assertEqual(
            self.resolve({"capability.service"}),
            [
                "capability.runtime",
                "capability.service",
                "lifecycle.composition-state",
                "lifecycle.contract-evolution",
                "lifecycle.implementation-evidence",
                "lifecycle.lifecycle-checkpoints",
            ],
        )

    def test_full_skill_capability_selection_has_single_portable_owners(self):
        recipe = self.recipes["skill"]
        selected = self.resolve(
            {recipe["artifact"], *recipe["required_components"], *recipe["default_components"], *recipe["optional_components"]}
        )
        destinations = [
            material["destination"]
            for component_id in selected
            for material in self.components[component_id]["materials"]
        ]
        self.assertEqual(len(destinations), len(set(destinations)))
        assert_no_portable_collisions(self, destinations)
        self.assertNotIn("INTERFACES.md", destinations)

    def test_materialized_full_skill_projection_validates(self):
        recipe = self.recipes["skill"]
        selected = self.resolve(
            {recipe["artifact"], *recipe["required_components"], *recipe["default_components"], *recipe["optional_components"]}
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            for component_id in selected:
                descriptor = self.components[component_id]
                component_root = component_path(component_id).parent
                for material in descriptor["materials"]:
                    if "source" not in material:
                        continue
                    destination = target / material["destination"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(component_root / material["source"], destination)

            lock_dir = target / ".template-composition"
            lock_dir.mkdir(exist_ok=True)
            (lock_dir / "lock.json").write_text(
                json.dumps(
                    {"resolved_components": [{"id": component_id} for component_id in selected]},
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(target / ".github/scripts/validate_skill.py"), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_minimal_skill_scaffold_validates_without_capabilities(self):
        files_root = ROOT / "components" / "artifact.skill-core" / "files"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            shutil.copytree(files_root, target, dirs_exist_ok=True)
            result = subprocess.run(
                [sys.executable, str(target / ".github/scripts/validate_skill.py"), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_instruction_only_skill_validates_with_managed_validator_outside_helper_namespace(self):
        files_root = ROOT / "components" / "artifact.skill-core" / "files"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            shutil.copytree(files_root, target, dirs_exist_ok=True)
            skill_path = target / "SKILL.md"
            skill_path.write_text(
                skill_path.read_text(encoding="utf-8").replace(
                    "Selected profiles: template-scaffold",
                    "Selected profiles: instruction-only",
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(target / ".github/scripts/validate_skill.py"), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((target / "scripts").exists())

    def test_legacy_application_profile_tag_is_rejected(self):
        files_root = ROOT / "components" / "artifact.skill-core" / "files"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            shutil.copytree(files_root, target, dirs_exist_ok=True)
            skill_path = target / "SKILL.md"
            skill_path.write_text(
                skill_path.read_text(encoding="utf-8").replace(
                    "Selected profiles: template-scaffold",
                    "Selected profiles: packaged-cli",
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(target / ".github/scripts/validate_skill.py"), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy application profile tags are composition capabilities", result.stderr)


if __name__ == "__main__":
    unittest.main()
