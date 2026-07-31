from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class ContractValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)
        route_schema = validate_contracts.load_json(ROOT / "schemas/routes.schema.json")
        self.route_validator = Draft202012Validator(route_schema)

    def route_document_is_valid(self, route: dict[str, object]) -> bool:
        document = {
            "$schema": "../schemas/routes.schema.json",
            "schemaVersion": 1,
            "routes": [route],
        }
        return self.route_validator.is_valid(document)

    def test_repository_contracts_are_valid(self) -> None:
        self.assertEqual([], validate_contracts.validate_repository(ROOT))

    def test_unknown_route_surface_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["routes"]["routes"][0]["surface"] = "missing-surface"
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("unknown surface missing-surface" in error for error in errors))

    def test_surface_dependency_cycle_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        surfaces = documents["surfaces"]["surfaces"]
        surfaces[0]["startupDependencies"] = [surfaces[1]["id"]]
        surfaces[1]["startupDependencies"] = [surfaces[0]["id"]]
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("dependency cycle" in error for error in errors))

    def test_viewport_gap_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["viewports"]["viewports"][1]["minWidthPx"] = 800
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("viewport boundary compact -> regular: gap" in error for error in errors))

    def test_route_path_rejects_query_and_fragment_delimiters(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        for invalid_path in ("/search?q=x", "/settings#profile"):
            with self.subTest(path=invalid_path):
                route["path"] = invalid_path
                self.assertFalse(self.route_document_is_valid(route))

    def test_route_contract_requires_canonical_routes(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        route["canonical"] = False
        self.assertFalse(self.route_document_is_valid(route))

    def test_unsupported_fixed_authentication_return_is_rejected(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        route["authenticationReturn"] = "fixed-route"
        self.assertFalse(self.route_document_is_valid(route))


if __name__ == "__main__":
    unittest.main()
