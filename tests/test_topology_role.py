from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core_impl as core
import composer_managed_impl as managed


from unittest.mock import patch

class TopologyRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch.object(core, "source_revision", return_value="1" * 40):
            cls.state = core.load_source_state()
        cls.component_schema = core.read_json(ROOT / "schemas/component.schema.json")
        cls.recipe_schema = core.read_json(ROOT / "schemas/recipe.schema.json")
        cls.config_schema = core.read_json(ROOT / "schemas/composition-config.schema.json")
        cls.lock_schema = core.read_json(ROOT / "schemas/composition-lock.schema.json")

    def test_topology_role_descriptor_schema_validation(self) -> None:
        valid_descriptor = {
            "schema_version": 1,
            "id": "topology.test",
            "component_role": "topology",
            "version": 1,
            "summary": "Test topology component",
            "requires": [],
            "conflicts": [],
            "materials": [
                {
                    "source": "files/test.json",
                    "destination": "contracts/test.json",
                    "ownership": "managed",
                }
            ],
        }
        Draft202012Validator(self.component_schema).validate(valid_descriptor)

        # Mismatched role and prefix: role=topology, id=capability.test
        invalid_role = copy.deepcopy(valid_descriptor)
        invalid_role["id"] = "capability.test"
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(invalid_role)

        # Mismatched role and prefix: role=capability, id=topology.test
        invalid_prefix = copy.deepcopy(valid_descriptor)
        invalid_prefix["component_role"] = "capability"
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(invalid_prefix)

    def test_topology_cannot_reference_artifact(self) -> None:
        descriptor = {
            "schema_version": 1,
            "id": "topology.test",
            "component_role": "topology",
            "version": 1,
            "summary": "Test topology",
            "requires": ["artifact.skill-core"],
            "conflicts": [],
            "materials": [
                {
                    "source": "files/test.json",
                    "destination": "contracts/test.json",
                    "ownership": "managed",
                }
            ],
        }
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(descriptor)

        descriptor["requires"] = []
        descriptor["conflicts"] = ["artifact.webapp-core"]
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(descriptor)

    def test_artifact_cannot_reference_topology(self) -> None:
        descriptor = {
            "schema_version": 1,
            "id": "artifact.test",
            "component_role": "artifact",
            "version": 1,
            "summary": "Test artifact",
            "requires": ["topology.test"],
            "conflicts": [],
            "materials": [
                {
                    "source": "files/test.json",
                    "destination": "test.txt",
                    "ownership": "managed",
                }
            ],
        }
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(descriptor)

        descriptor["requires"] = []
        descriptor["conflicts"] = ["topology.test"]
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.component_schema).validate(descriptor)

    def test_resolver_enforces_at_most_one_topology_component(self) -> None:
        mock_state = copy.deepcopy(self.state)
        # Inject two synthetic topology components
        mock_state.components["topology.topo-a"] = {
            "schema_version": 1,
            "id": "topology.topo-a",
            "component_role": "topology",
            "version": 1,
            "summary": "Topology A",
            "requires": [],
            "conflicts": [],
            "materials": [
                {
                    "source": "files/a.json",
                    "destination": "contracts/a.json",
                    "ownership": "managed",
                }
            ],
        }
        mock_state.components["topology.topo-b"] = {
            "schema_version": 1,
            "id": "topology.topo-b",
            "component_role": "topology",
            "version": 1,
            "summary": "Topology B",
            "requires": [],
            "conflicts": [],
            "materials": [
                {
                    "source": "files/b.json",
                    "destination": "contracts/b.json",
                    "ownership": "managed",
                }
            ],
        }
        mock_state.recipes["skill"]["optional_components"].extend(["topology.topo-a", "topology.topo-b"])

        # Resolving with one topology succeeds
        config_one = {
            "schema_version": 1,
            "recipe": "skill",
            "components": {
                "include": ["topology.topo-a"],
                "exclude": [],
            },
            "parameters": {},
        }
        recipe, resolved = core.resolve_configuration(mock_state, config_one)
        self.assertIn("topology.topo-a", resolved)
        self.assertNotIn("topology.topo-b", resolved)

        # Resolving with two topologies fails
        config_two = {
            "schema_version": 1,
            "recipe": "skill",
            "components": {
                "include": ["topology.topo-a", "topology.topo-b"],
                "exclude": [],
            },
            "parameters": {},
        }
        with self.assertRaises(core.CompositionError) as ctx:
            core.resolve_configuration(mock_state, config_two)
        self.assertEqual(ctx.exception.code, "MULTIPLE_TOPOLOGY_COMPONENTS")

    def test_absence_of_topology_retains_conventional_state(self) -> None:
        config = {
            "schema_version": 1,
            "recipe": "skill",
            "components": {
                "include": [],
                "exclude": [],
            },
            "parameters": {},
        }
        recipe, resolved = core.resolve_configuration(self.state, config)
        topologies = [cid for cid in resolved if cid.startswith("topology.")]
        self.assertEqual([], topologies)

    def test_managed_old_lock_rejects_multiple_topologies(self) -> None:
        lock = {
            "schema_version": 1,
            "repository": core.CANONICAL_REPOSITORY,
            "source_revision": "a" * 40,
            "intent": {
                "recipe": "skill",
                "components": {"include": ["topology.a", "topology.b"], "exclude": []},
                "parameters": {},
            },
            "recipe_sha256": "0" * 64,
            "configuration_sha256": "0" * 64,
            "resolved_components": [
                {"id": "artifact.skill-core", "version": 1, "descriptor_sha256": "0" * 64},
                {"id": "topology.a", "version": 1, "descriptor_sha256": "0" * 64},
                {"id": "topology.b", "version": 1, "descriptor_sha256": "0" * 64},
            ],
            "files": [
                {"destination": "a.txt", "component": "artifact.skill-core", "ownership": "managed", "materialized_sha256": "0" * 64},
                {"destination": "topo-a.txt", "component": "topology.a", "ownership": "managed", "materialized_sha256": "0" * 64},
                {"destination": "topo-b.txt", "component": "topology.b", "ownership": "managed", "materialized_sha256": "0" * 64},
            ],
        }
        with self.assertRaises(managed.ManagedPlanError) as ctx:
            managed._validate_lock_semantics(lock)
        self.assertEqual(ctx.exception.code, "INVALID_OLD_LOCK")
        self.assertIn("at most one topology component", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
