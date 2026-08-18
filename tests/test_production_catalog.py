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
CATALOG = ROOT / "catalog/catalog.json"
COMPONENT_SCHEMA = ROOT / "schemas/component.schema.json"
RECIPE_SCHEMA = ROOT / "schemas/recipe.schema.json"
CATALOG_SCHEMA = ROOT / "schemas/catalog.schema.json"
SUPPORTED_GENERATORS = {"contract-manifest-v1"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def component_path(component_id: str) -> Path:
    return ROOT / "components" / component_id / "component.json"


def recipe_path(recipe_id: str) -> Path:
    return ROOT / "recipes" / f"{recipe_id}.json"


def assert_no_portable_collisions(test: unittest.TestCase, destinations: list[str]) -> None:
    seen: dict[str, str] = {}
    reserved = ".template-composition/lock.json"
    for destination in sorted(destinations, key=lambda value: (value.casefold(), value)):
        key = destination.casefold()
        test.assertFalse(key == reserved or key.startswith(reserved + "/") or reserved.startswith(key + "/"), f"destination conflicts with reserved lock path: {destination}")
        test.assertNotIn(key, seen, f"case-insensitive destination collision: {seen.get(key)} / {destination}")
        seen[key] = destination
    keys = set(seen)
    for destination in destinations:
        parts = destination.split("/")
        for index in range(1, len(parts)):
            test.assertNotIn("/".join(parts[:index]).casefold(), keys, f"file/directory collision: {destination}")


class ProductionCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load(CATALOG)
        cls.component_schema = load(COMPONENT_SCHEMA)
        cls.recipe_schema = load(RECIPE_SCHEMA)
        cls.catalog_schema = load(CATALOG_SCHEMA)
        cls.components = {cid: load(component_path(cid)) for cid in cls.catalog["components"]}
        cls.recipes = {rid: load(recipe_path(rid)) for rid in cls.catalog["recipes"]}

    def resolve(self, initial) -> list[str]:
        resolved = set(initial)
        changed = True
        while changed:
            changed = False
            for cid in list(resolved):
                for dependency in self.components[cid]["requires"]:
                    if dependency not in resolved:
                        resolved.add(dependency); changed = True
        for cid in resolved:
            self.assertFalse(set(self.components[cid]["conflicts"]) & resolved, f"selected conflict for {cid}")
        return sorted(resolved)

    def render_manifest(self, selected) -> dict:
        registrations = []
        for cid in sorted(selected):
            for registration in self.components[cid].get("contract_registrations", []):
                history = []
                for item in registration["version_history"]:
                    rendered = {"version": item["version"], "changeType": item["change_type"]}
                    if "migration" in item: rendered["migration"] = item["migration"]
                    history.append(rendered)
                registrations.append({"id": registration["id"], "document": registration["document"], "schema": registration["schema"], "migrationSlug": registration["migration_slug"], "documentSchemaVersion": registration["document_schema_version"], "versionHistory": history, "purpose": registration["purpose"]})
        registrations.sort(key=lambda item: item["id"])
        return {"$schema": "../schemas/contract-manifest.schema.json", "schemaVersion": 1, "versionHistory": [{"version": 1, "changeType": "initial"}], "contracts": registrations, "retiredContracts": []}

    def materialize(self, selected, target: Path, *, write_lock: bool = False) -> None:
        for cid in selected:
            descriptor = self.components[cid]; root = component_path(cid).parent
            for material in descriptor["materials"]:
                if "source" not in material: continue
                destination = target / material["destination"]; destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(root / material["source"], destination)
        if "lifecycle.contract-evolution" in selected:
            path = target / "contracts/manifest.json"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(self.render_manifest(selected), indent=2) + "\n", encoding="utf-8")
        if write_lock:
            lock = target / ".template-composition/lock.json"; lock.parent.mkdir(parents=True, exist_ok=True); lock.write_text(json.dumps({"resolved_components": [{"id": cid} for cid in sorted(selected)]}, indent=2) + "\n", encoding="utf-8")

    def run_script(self, target: Path, relative: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(target / relative), *args], cwd=target, text=True, capture_output=True, check=False)

    def test_catalog_schema_and_closed_inventory(self):
        Draft202012Validator.check_schema(self.catalog_schema); Draft202012Validator(self.catalog_schema).validate(self.catalog)
        self.assertEqual(self.catalog["components"], sorted(self.catalog["components"])); self.assertEqual(self.catalog["recipes"], sorted(self.catalog["recipes"]))
        self.assertEqual(sorted(path.name for path in (ROOT / "components").iterdir() if path.is_dir()), self.catalog["components"])
        self.assertEqual(sorted(path.stem for path in (ROOT / "recipes").glob("*.json")), self.catalog["recipes"])

    def test_component_descriptors_sources_and_dependencies_are_closed(self):
        validator = Draft202012Validator(self.component_schema); ids = set(self.components)
        for cid, descriptor in self.components.items():
            with self.subTest(component=cid):
                validator.validate(descriptor); self.assertEqual(descriptor["id"], cid); self.assertEqual(descriptor["kind"], cid.split(".", 1)[0]); self.assertNotIn(cid, descriptor["requires"]); self.assertFalse(set(descriptor["requires"]) & set(descriptor["conflicts"]))
                for reference in descriptor["requires"] + descriptor["conflicts"]: self.assertIn(reference, ids)
                if descriptor["kind"] in {"capability", "lifecycle"}: self.assertFalse(any(x.startswith("artifact.") for x in descriptor["requires"] + descriptor["conflicts"]))
                component_root = component_path(cid).parent; declared = sorted(x["source"] for x in descriptor["materials"] if "source" in x)
                actual_paths = [path for path in (component_root / "files").rglob("*") if path.is_file() or path.is_symlink()]
                for path in actual_paths: self.assertFalse(path.is_symlink(), f"component source material must not be a symlink: {cid}/{path.relative_to(component_root)}")
                self.assertEqual(sorted(path.relative_to(component_root).as_posix() for path in actual_paths), declared)
                for material in descriptor["materials"]:
                    if material["ownership"] == "generated": self.assertIn(material["generator"], SUPPORTED_GENERATORS)

    def test_dependency_graph_is_acyclic(self):
        visiting, visited = set(), set()
        def visit(cid):
            if cid in visited: return
            self.assertNotIn(cid, visiting, f"dependency cycle at {cid}"); visiting.add(cid)
            for dep in self.components[cid]["requires"]: visit(dep)
            visiting.remove(cid); visited.add(cid)
        for cid in self.catalog["components"]: visit(cid)

    def test_contract_registrations_are_globally_unique_and_component_owned(self):
        ids, documents, schemas = set(), set(), set()
        for cid, descriptor in self.components.items():
            destinations = {m["destination"] for m in descriptor["materials"]}
            for registration in descriptor.get("contract_registrations", []):
                self.assertNotIn(registration["id"], ids); self.assertNotIn(registration["document"], documents); self.assertNotIn(registration["schema"], schemas)
                ids.add(registration["id"]); documents.add(registration["document"]); schemas.add(registration["schema"])
                self.assertIn(registration["document"], destinations); self.assertIn(registration["schema"], destinations)
                versions = [x["version"] for x in registration["version_history"]]; self.assertEqual(versions, list(range(1, registration["document_schema_version"] + 1)))
                for item in registration["version_history"][1:]: self.assertIn(item["migration"], destinations)

    def test_manifest_generated_owner_is_unique(self):
        owners = []
        for cid, descriptor in self.components.items():
            for material in descriptor["materials"]:
                if material["destination"] == "contracts/manifest.json": owners.append((cid, material["ownership"], material.get("generator")))
        self.assertEqual(owners, [("lifecycle.contract-evolution", "generated", "contract-manifest-v1")])

    def test_recipes_reference_closed_catalog(self):
        validator = Draft202012Validator(self.recipe_schema)
        for rid, recipe in self.recipes.items():
            validator.validate(recipe); self.assertEqual(recipe["id"], rid); self.assertIn(recipe["artifact"], self.components)
            groups = [recipe["required_components"], recipe["default_components"], recipe["optional_components"]]
            for group in groups: self.assertEqual(group, sorted(group))
            sets = list(map(set, groups)); self.assertFalse(sets[0] & sets[1]); self.assertFalse(sets[0] & sets[2]); self.assertFalse(sets[1] & sets[2])
            for cid in set().union(*sets): self.assertIn(cid, self.components); self.assertNotEqual(self.components[cid]["kind"], "artifact")

    def test_skill_recipe_exposes_capabilities_and_lifecycle(self):
        recipe = self.recipes["skill"]; self.assertEqual(recipe["artifact"], "artifact.skill-core")
        self.assertEqual(recipe["optional_components"], ["capability.cli", "capability.mcp", "capability.mcp-apps", "capability.runtime", "capability.service", "capability.web-interface", "lifecycle.contract-evolution", "lifecycle.implementation-evidence", "lifecycle.release-bundle", "lifecycle.release-evidence"])

    def test_webapp_recipe_uses_webapp_artifact_and_optional_capabilities(self):
        recipe = self.recipes["webapp"]; self.assertEqual(recipe["artifact"], "artifact.webapp-core"); self.assertEqual(recipe["required_components"], [])
        self.assertEqual(recipe["optional_components"], ["capability.cli", "capability.mcp", "capability.mcp-apps", "capability.runtime", "capability.service", "capability.web-interface"])
        closure = self.resolve({recipe["artifact"]})
        for lifecycle in ("lifecycle.contract-evolution", "lifecycle.implementation-evidence", "lifecycle.release-evidence", "lifecycle.release-bundle"): self.assertIn(lifecycle, closure)

    def test_dependency_closures(self):
        self.assertEqual(self.resolve({"capability.mcp-apps"}), ["capability.mcp", "capability.mcp-apps", "capability.runtime"])
        self.assertEqual(self.resolve({"lifecycle.release-bundle"}), ["lifecycle.contract-evolution", "lifecycle.implementation-evidence", "lifecycle.release-bundle", "lifecycle.release-evidence"])

    def test_recipe_unions_have_portable_single_owners(self):
        for rid, recipe in self.recipes.items():
            selected = self.resolve({recipe["artifact"], *recipe["required_components"], *recipe["default_components"], *recipe["optional_components"]})
            destinations = [material["destination"] for cid in selected for material in self.components[cid]["materials"]]
            self.assertEqual(len(destinations), len(set(destinations)), rid); assert_no_portable_collisions(self, destinations)

    def test_generated_manifest_is_deterministic(self):
        selected = self.resolve({"artifact.webapp-core", "capability.mcp-apps"}); self.assertEqual(self.render_manifest(selected), self.render_manifest(reversed(selected)))

    def test_minimal_skill_scaffold_validates_without_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp); self.materialize(["artifact.skill-core"], target); result = self.run_script(target, ".github/scripts/validate_skill.py", "."); self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_instruction_only_skill_validates(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp); self.materialize(["artifact.skill-core"], target); skill = target / "SKILL.md"; skill.write_text(skill.read_text(encoding="utf-8").replace("Selected profiles: template-scaffold", "Selected profiles: instruction-only"), encoding="utf-8"); result = self.run_script(target, ".github/scripts/validate_skill.py", "."); self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertFalse((target / "scripts").exists())

    def test_legacy_skill_application_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp); self.materialize(["artifact.skill-core"], target); skill = target / "SKILL.md"; skill.write_text(skill.read_text(encoding="utf-8").replace("Selected profiles: template-scaffold", "Selected profiles: packaged-cli"), encoding="utf-8"); result = self.run_script(target, ".github/scripts/validate_skill.py", "."); self.assertNotEqual(result.returncode, 0); self.assertIn("legacy application profile tags are composition capabilities", result.stderr)

    def test_full_skill_projection_with_lifecycle_validates(self):
        recipe = self.recipes["skill"]; selected = self.resolve({recipe["artifact"], *recipe["optional_components"]})
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp); self.materialize(selected, target, write_lock=True); skill = self.run_script(target, ".github/scripts/validate_skill.py", "."); self.assertEqual(skill.returncode, 0, skill.stdout + skill.stderr)
            for script in (".template-composition/validators/validate_contract_evolution.py", ".template-composition/validators/validate_implementation_evidence.py", ".template-composition/validators/validate_release_evidence.py", ".template-composition/validators/validate_release_bundle.py"):
                result = self.run_script(target, script, "."); self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_webapp_template_projection_validates(self):
        recipe = self.recipes["webapp"]; selected = self.resolve({recipe["artifact"]})
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp); self.materialize(selected, target)
            for script in ("scripts/validate_contracts.py", ".template-composition/validators/validate_contract_evolution.py", ".template-composition/validators/validate_implementation_evidence.py", "scripts/validate_webapp_evidence.py", ".template-composition/validators/validate_release_evidence.py", ".template-composition/validators/validate_release_bundle.py"):
                result = self.run_script(target, script) if script in {"scripts/validate_contracts.py", "scripts/validate_webapp_evidence.py"} else self.run_script(target, script, ".")
                self.assertEqual(result.returncode, 0, f"{script}\n{result.stdout}{result.stderr}")

    def test_webapp_manifest_preserves_domain_versions(self):
        selected = self.resolve({"artifact.webapp-core"}); entries = {entry["id"]: entry for entry in self.render_manifest(selected)["contracts"]}
        self.assertEqual(set(entries), {"implementation_evidence", "release_bundle", "release_evidence", "routes", "surfaces", "ui_states", "viewports"}); self.assertEqual(entries["routes"]["documentSchemaVersion"], 2); self.assertEqual(entries["ui_states"]["documentSchemaVersion"], 2); self.assertEqual([x["version"] for x in entries["routes"]["versionHistory"]], [1, 2]); self.assertEqual([x["version"] for x in entries["ui_states"]["versionHistory"]], [1, 2])


if __name__ == "__main__": unittest.main()
