from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "components/workspace.bare-worktree/files"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core_impl as core

SPEC = importlib.util.spec_from_file_location(
    "local_checkout_validator",
    FILES / ".template-composition/validators/validate_local_checkout_topology.py",
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class BareWorktreeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((FILES / "contracts/local-checkout-topology.json").read_text())
        cls.schema = json.loads((FILES / "schemas/local-checkout-topology.schema.json").read_text())

    def test_contract_and_descriptor_are_valid(self) -> None:
        Draft202012Validator(self.schema).validate(self.contract)
        self.assertEqual([], validator.validate_contract(self.contract, self.schema))
        descriptor = json.loads((ROOT / "components/workspace.bare-worktree/component.json").read_text())
        self.assertEqual("workspace", descriptor["component_role"])
        self.assertEqual("workspace.bare-worktree", descriptor["id"])
        self.assertEqual("local_checkout_topology", descriptor["contract_registrations"][0]["id"])

    def test_invalid_contracts_fail_closed(self) -> None:
        for mutation in (
            lambda value: value.__setitem__("topologyKind", "single-worktree"),
            lambda value: value.__setitem__("commonGitDirectory", "../outside"),
            lambda value: value["layout"].__setitem__("workspaceRootIsWorktree", True),
            lambda value: value.__setitem__("rootGitIndirection", "required"),
        ):
            value = copy.deepcopy(self.contract)
            mutation(value)
            with self.subTest(value=value):
                with self.assertRaises((ValidationError, validator.LocalCheckoutTopologyValidationError)):
                    validator.validate_contract(value, self.schema)

    def test_validator_rejects_symlinked_declaration_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contracts").mkdir()
            (root / "schemas").mkdir()
            (root / "schemas/local-checkout-topology.schema.json").write_text(json.dumps(self.schema))
            target = root / "contract-source.json"
            target.write_text(json.dumps(self.contract))
            (root / "contracts/local-checkout-topology.json").symlink_to(target)
            with self.assertRaises(validator.LocalCheckoutTopologyValidationError):
                validator.validate_local_checkout_topology(root)

    def test_hub_and_orphan_and_bare_worktree_resolve_and_materialize(self) -> None:
        with patch.object(core, "source_revision", return_value="1" * 40):
            state = core.load_source_state()
        config = {
            "schema_version": 1,
            "recipe": "skill",
            "components": {"include": ["topology.hub-and-orphan", "workspace.bare-worktree"], "exclude": []},
            "parameters": {},
        }
        _, resolved = core.resolve_configuration(state, config)
        self.assertIn("topology.hub-and-orphan", resolved)
        self.assertIn("workspace.bare-worktree", resolved)
        materials = core.build_materials(state, resolved)
        destinations = [material.destination for material in materials]
        self.assertEqual(len(destinations), len(set(destinations)))
        with tempfile.TemporaryDirectory() as directory:
            actions, conflicts = core.plan_target(Path(directory), materials)
        self.assertFalse(conflicts)
        self.assertTrue(actions)


if __name__ == "__main__":
    unittest.main()
