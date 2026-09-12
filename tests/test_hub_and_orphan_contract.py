from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "components/topology.hub-and-orphan/files"
spec = importlib.util.spec_from_file_location(
    "topology_validator", FILES / ".template-composition/validators/validate_repository_topology.py"
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class HubAndOrphanContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((FILES / "contracts/repository-topology.json").read_text())
        self.schema = json.loads((FILES / "schemas/repository-topology.schema.json").read_text())

    def component(self, branch):
        return {"name": "example", "branch": branch, "mountPath": branch,
                "role": "component-authority"}

    def test_seed_and_custom_hub_are_valid(self):
        self.assertEqual([], validator.validate_contract(self.contract, self.schema))
        self.contract["hub"]["branch"] = "portal"
        self.contract["components"] = [self.component("packages/core")]
        self.assertEqual([], validator.validate_contract(self.contract, self.schema))

    def test_git_ref_and_hub_namespace_boundaries(self):
        for branch in ("HEAD", "-core", "core..v1", "core.lock", "core.", "main/core"):
            with self.subTest(branch=branch):
                self.contract["components"] = [self.component(branch)]
                self.assertTrue(validator.validate_contract(self.contract, self.schema))

    def test_branch_mount_and_nested_namespaces_fail(self):
        self.contract["components"] = [self.component("core")]
        self.contract["components"][0]["mountPath"] = "other"
        self.assertTrue(validator.validate_contract(self.contract, self.schema))
        self.contract["components"] = [self.component("core"), self.component("core/api")]
        self.contract["components"][1]["name"] = "api"
        self.assertTrue(validator.validate_contract(self.contract, self.schema))

    def test_missing_dependency_fails_closed(self):
        with patch.dict("sys.modules", {"jsonschema": None}):
            with self.assertRaises(validator.TopologyValidationError):
                validator.validate_contract(self.contract, self.schema)

    def test_unknown_fields_are_rejected(self):
        data = copy.deepcopy(self.contract)
        data["executeHook"] = "arbitrary-command"
        with self.assertRaises(validator.TopologyValidationError):
            validator.validate_contract(data, self.schema)


if __name__ == "__main__":
    unittest.main()
