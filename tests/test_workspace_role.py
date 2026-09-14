from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core_impl as core

VALIDATOR_PATH = (
    ROOT
    / "components"
    / "lifecycle.composition-state"
    / "files"
    / ".template-composition"
    / "validate_composition.py"
)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "materialized_composition_validator", VALIDATOR_PATH
)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
materialized_validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(materialized_validator)


def descriptor(component_id: str, role: str) -> dict:
    return {
        "schema_version": 1,
        "id": component_id,
        "component_role": role,
        "version": 1,
        "summary": f"Synthetic {role} component",
        "requires": [],
        "conflicts": [],
        "materials": [
            {
                "source": "files/test.json",
                "destination": f"contracts/{component_id.replace('.', '-')}.json",
                "ownership": "managed",
            }
        ],
    }


class WorkspaceRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch.object(core, "source_revision", return_value="1" * 40):
            cls.state = core.load_source_state()
        cls.component_schema = core.read_json(ROOT / "schemas/component.schema.json")

    def test_workspace_role_requires_workspace_namespace_and_is_generic(self) -> None:
        valid = descriptor("workspace.test", "workspace")
        Draft202012Validator(self.component_schema).validate(valid)

        wrong_namespace = copy.deepcopy(valid)
        wrong_namespace["id"] = "topology.test"
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(wrong_namespace)

        generic_artifact_dependency = copy.deepcopy(valid)
        generic_artifact_dependency["requires"] = ["artifact.skill-core"]
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(generic_artifact_dependency)

    def test_workspace_cardinality_is_independent_from_topology(self) -> None:
        state = copy.deepcopy(self.state)
        state.components["topology.synthetic"] = descriptor("topology.synthetic", "topology")
        state.components["workspace.one"] = descriptor("workspace.one", "workspace")
        state.components["workspace.two"] = descriptor("workspace.two", "workspace")
        state.recipes["skill"]["optional_components"].extend(
            ["topology.synthetic", "workspace.one", "workspace.two"]
        )

        config = {
            "schema_version": 1,
            "recipe": "skill",
            "components": {
                "include": ["topology.synthetic", "workspace.one"],
                "exclude": [],
            },
            "parameters": {},
        }
        _, resolved = core.resolve_configuration(state, config)
        self.assertIn("topology.synthetic", resolved)
        self.assertIn("workspace.one", resolved)

        config["components"]["include"].append("workspace.two")
        with self.assertRaises(core.CompositionError) as context:
            core.resolve_configuration(state, config)
        self.assertEqual("MULTIPLE_WORKSPACE_COMPONENTS", context.exception.code)

    def test_materialized_lock_accepts_one_workspace_and_rejects_two(self) -> None:
        digest = "1" * 64
        lock = {
            "schema_version": 2,
            "source": {
                "repository": "TakashiSasaki/templates",
                "revision": "1" * 40,
            },
            "intent": {
                "recipe": "skill",
                "components": {
                    "include": ["workspace.one"],
                    "exclude": [],
                },
                "parameters": {"workspace.one": {}},
            },
            "recipe_sha256": digest,
            "configuration_sha256": digest,
            "resolved_components": [
                {"id": "artifact.skill-core", "version": 1, "descriptor_sha256": digest},
                {"id": "workspace.one", "version": 1, "descriptor_sha256": digest},
            ],
            "files": [
                {
                    "destination": "README.md",
                    "component": "artifact.skill-core",
                    "ownership": "seed",
                    "materialized_sha256": digest,
                },
                {
                    "destination": "contracts/workspace-one.json",
                    "component": "workspace.one",
                    "ownership": "managed",
                    "materialized_sha256": digest,
                },
            ],
        }
        self.assertEqual([], materialized_validator.validate_lock_shape(lock))

        lock["resolved_components"].append(
            {"id": "workspace.two", "version": 1, "descriptor_sha256": digest}
        )
        lock["resolved_components"].sort(key=lambda entry: entry["id"])
        errors = materialized_validator.validate_lock_shape(lock)
        self.assertIn(
            "composition lock must resolve at most one workspace component", errors
        )


if __name__ == "__main__":
    unittest.main()
