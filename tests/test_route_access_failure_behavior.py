from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


DEFAULT_ACCESS_FAILURES = {
    "home": {"unauthenticated": "not-applicable", "forbidden": "not-applicable"},
    "application-home": {"unauthenticated": "render-state", "forbidden": "render-state"},
    "status": {"unauthenticated": "not-applicable", "forbidden": "not-applicable"},
}


class RouteAccessFailureBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)

    @staticmethod
    def assign_access_failures(documents: dict[str, Any]) -> None:
        for route in documents["routes"]["routes"]:
            route["accessFailures"] = copy.deepcopy(DEFAULT_ACCESS_FAILURES[route["id"]])

    def test_route_schema_requires_access_failures_at_version_two(self) -> None:
        document = copy.deepcopy(self.documents["routes"])
        document["schemaVersion"] = 2
        self.assign_access_failures({"routes": document})
        schema = validate_contracts.load_json(ROOT / "schemas/routes.schema.json")
        validator = Draft202012Validator(schema)

        self.assertTrue(validator.is_valid(document))

        del document["routes"][0]["accessFailures"]
        self.assertFalse(validator.is_valid(document))

    def test_route_schema_rejects_unknown_access_failure_behavior(self) -> None:
        document = copy.deepcopy(self.documents["routes"])
        document["schemaVersion"] = 2
        self.assign_access_failures({"routes": document})
        document["routes"][0]["accessFailures"]["unauthenticated"] = "modal"
        schema = validate_contracts.load_json(ROOT / "schemas/routes.schema.json")

        self.assertFalse(Draft202012Validator(schema).is_valid(document))

    def test_manifest_registers_routes_schema_version_two(self) -> None:
        manifest = validate_contracts.load_contract_manifest(ROOT)
        routes_entry = next(entry for entry in manifest["contracts"] if entry["id"] == "routes")

        self.assertEqual(2, routes_entry["documentSchemaVersion"])

    def test_example_routes_have_reviewed_access_failure_behavior(self) -> None:
        routes = {
            route["id"]: route["accessFailures"]
            for route in self.documents["routes"]["routes"]
        }

        self.assertEqual(DEFAULT_ACCESS_FAILURES, routes)

    def test_required_authentication_rejects_not_applicable_unauthenticated_failure(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_access_failures(documents)
        route = next(route for route in documents["routes"]["routes"] if route["id"] == "application-home")
        route["accessFailures"]["unauthenticated"] = "not-applicable"
        route["states"].remove("unauthorized")

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route application-home: required authentication must declare unauthenticated access failure as render-state or redirect",
            errors,
        )

    def test_optional_authentication_requires_unauthenticated_not_applicable(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_access_failures(documents)
        route = next(route for route in documents["routes"]["routes"] if route["id"] == "home")
        route["accessFailures"]["unauthenticated"] = "render-state"
        route["states"].append("unauthorized")

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route home: optional authentication requires unauthenticated access failure not-applicable",
            errors,
        )

    def test_role_authorization_rejects_not_applicable_forbidden_failure(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_access_failures(documents)
        route = next(route for route in documents["routes"]["routes"] if route["id"] == "application-home")
        route["accessFailures"]["forbidden"] = "not-applicable"
        route["states"].remove("forbidden")

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route application-home: role authorization must declare forbidden access failure as render-state or redirect",
            errors,
        )

    def test_public_authorization_requires_forbidden_not_applicable(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_access_failures(documents)
        route = next(route for route in documents["routes"]["routes"] if route["id"] == "home")
        route["accessFailures"]["forbidden"] = "render-state"
        route["states"].append("forbidden")

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route home: public authorization requires forbidden access failure not-applicable",
            errors,
        )

    def test_render_state_requires_corresponding_access_state(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_access_failures(documents)
        route = next(route for route in documents["routes"]["routes"] if route["id"] == "application-home")
        route["states"].remove("unauthorized")
        route["states"].remove("forbidden")

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route application-home: unauthenticated access failure render-state requires UI state unauthorized",
            errors,
        )
        self.assertIn(
            "route application-home: forbidden access failure render-state requires UI state forbidden",
            errors,
        )

    def test_redirect_must_not_declare_corresponding_access_state(self) -> None:
        documents = copy.deepcopy(self.documents)
        self.assign_access_failures(documents)
        route = next(route for route in documents["routes"]["routes"] if route["id"] == "application-home")
        route["accessFailures"]["unauthenticated"] = "redirect"
        route["accessFailures"]["forbidden"] = "redirect"

        errors = validate_contracts.cross_validate(documents)

        self.assertIn(
            "route application-home: unauthenticated access failure redirect must not declare UI state unauthorized",
            errors,
        )
        self.assertIn(
            "route application-home: forbidden access failure redirect must not declare UI state forbidden",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
