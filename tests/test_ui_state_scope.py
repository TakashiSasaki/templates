from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


GLOBAL_STATE_IDS = {"fatal-error", "retrying", "not-found"}


class UIStateScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)

    @staticmethod
    def assign_scopes(documents: dict[str, object]) -> None:
        states = documents["ui_states"]["states"]
        for state in states:
            state["scope"] = "global" if state["id"] in GLOBAL_STATE_IDS else "route"

    def test_ui_state_schema_requires_scope_at_version_two(self) -> None:
        document = copy.deepcopy(self.documents["ui_states"])
        self.assign_scopes({"ui_states": document})
        document["schemaVersion"] = 2
        schema = validate_contracts.load_json(ROOT / "schemas/ui-states.schema.json")
        validator = Draft202012Validator(schema)

        self.assertTrue(validator.is_valid(document))

        del document["states"][0]["scope"]
        self.assertFalse(validator.is_valid(document))

    def test_ui_state_schema_rejects_unknown_scope(self) -> None:
        document = copy.deepcopy(self.documents["ui_states"])
        self.assign_scopes({"ui_states": document})
        document["schemaVersion"] = 2
        document["states"][0]["scope"] = "component"
        schema = validate_contracts.load_json(ROOT / "schemas/ui-states.schema.json")

        self.assertFalse(Draft202012Validator(schema).is_valid(document))

    def test_route_scoped_state_requires_a_route_reference(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_scopes(documents)
        for route in documents["routes"]["routes"]:
            route["states"] = [state_id for state_id in route["states"] if state_id != "empty"]

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "UI state empty: route-scoped state is not declared by any route",
            errors,
        )

    def test_global_state_must_not_be_declared_by_a_route(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_scopes(documents)
        documents["routes"]["routes"][0]["states"].append("not-found")

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route home: global UI state not-found must not be declared by a route",
            errors,
        )

    def test_unreferenced_global_states_are_valid(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_scopes(documents)

        errors = validate_contracts.cross_validate(documents)

        self.assertFalse(any("route-scoped state" in error for error in errors))
        self.assertFalse(any("global UI state" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
