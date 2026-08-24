from __future__ import annotations

import copy
import json
import sys
import types
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "components" / "artifact.webapp-core" / "files"
VALIDATOR_IMPL = WEBAPP / "scripts" / "validate_contracts_impl.py"


def load_module_without_bytecode(name: str, path: Path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


validator_impl = load_module_without_bytecode(
    "webapp_surface_dependencies_v2_validator", VALIDATOR_IMPL
)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class WebappSurfaceDependenciesV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load_json(WEBAPP / "schemas" / "surfaces.schema.json")
        self.surfaces = load_json(WEBAPP / "contracts" / "surfaces.json")
        documents = {
            "surfaces": copy.deepcopy(self.surfaces),
            "routes": load_json(WEBAPP / "contracts" / "routes.json"),
            "ui_states": load_json(WEBAPP / "contracts" / "ui-states.json"),
            "viewports": load_json(WEBAPP / "contracts" / "viewports.json"),
        }
        application = copy.deepcopy(documents["surfaces"]["surfaces"][0])
        application.update(
            {
                "id": "application",
                "title": "Application surface",
                "purpose": "Exercise explicit cross-surface dependency semantics.",
            }
        )
        documents["surfaces"]["surfaces"].append(application)
        self.documents = documents

    def test_canonical_surfaces_use_v2_surface_dependency_member(self) -> None:
        self.assertEqual(self.surfaces["schemaVersion"], 2)
        self.assertEqual(
            list(Draft202012Validator(self.schema).iter_errors(self.surfaces)), []
        )
        for surface in self.surfaces["surfaces"]:
            self.assertIn("surfaceDependencies", surface)
            self.assertNotIn("startupDependencies", surface)

    def test_v2_rejects_legacy_startup_dependencies_member(self) -> None:
        legacy = copy.deepcopy(self.surfaces)
        first = legacy["surfaces"][0]
        first["startupDependencies"] = first.pop("surfaceDependencies")
        errors = list(Draft202012Validator(self.schema).iter_errors(legacy))
        self.assertTrue(errors)
        rendered = "\n".join(error.message for error in errors)
        self.assertIn("surfaceDependencies", rendered)
        self.assertIn("startupDependencies", rendered)

    def test_unknown_surface_dependency_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["surfaces"]["surfaces"][1]["surfaceDependencies"] = ["missing"]
        errors = validator_impl.cross_validate(documents)
        self.assertIn("surface application: unknown surface dependency missing", errors)

    def test_self_surface_dependency_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["surfaces"]["surfaces"][1]["surfaceDependencies"] = [
            "application"
        ]
        errors = validator_impl.cross_validate(documents)
        self.assertIn("surface application: must not depend on itself", errors)

    def test_surface_dependency_cycle_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        surfaces = {
            surface["id"]: surface for surface in documents["surfaces"]["surfaces"]
        }
        surfaces["primary"]["surfaceDependencies"] = ["application"]
        surfaces["application"]["surfaceDependencies"] = ["primary"]
        errors = validator_impl.cross_validate(documents)
        self.assertTrue(
            any(error.startswith("surface dependency cycle: ") for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
