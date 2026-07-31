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

    def test_principal_authorization_requires_required_authentication(self) -> None:
        for mode, roles in (("authenticated", []), ("role", ["application-user"])):
            with self.subTest(mode=mode):
                documents = copy.deepcopy(self.documents)
                surface = documents["surfaces"]["surfaces"][1]
                route = documents["routes"]["routes"][1]
                surface["authentication"] = "none"
                surface["authorization"] = {"mode": mode, "roles": roles}
                route["authentication"] = "none"
                errors = validate_contracts.cross_validate(documents)
                self.assertTrue(
                    any(f"{mode} authorization requires authentication required" in error for error in errors)
                )

    def test_viewport_gap_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["viewports"]["viewports"][1]["minWidthPx"] = 800
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("viewport boundary compact -> regular: gap" in error for error in errors))

    def test_route_path_accepts_only_stable_unreserved_segments(self) -> None:
        original = self.documents["routes"]["routes"][0]
        for valid_path in ("/", "/.well-known", "/user_profile-1~draft", "/alpha/beta.gamma"):
            with self.subTest(path=valid_path):
                route = copy.deepcopy(original)
                route["path"] = valid_path
                self.assertTrue(self.route_document_is_valid(route))

    def test_route_path_rejects_normalized_or_unstable_forms(self) -> None:
        original = self.documents["routes"]["routes"][0]
        invalid_paths = (
            "/search?q=x",
            "/settings#profile",
            "/./admin",
            "/x/../admin",
            "/admin\\settings",
            "/x/%2e%2e/admin",
            "/x/%2E./admin",
            "/x/.%2e/admin",
            "/foo\nbar",
            "/foo\rbar",
            "/foo\tbar",
            "/foo\n",
            "/foo\r",
            "/foo\t",
            "/foo bar",
            "/é",
            "/\t/evil.example",
            "//evil.example",
            "/trailing/",
            "/double//slash",
        )
        for invalid_path in invalid_paths:
            with self.subTest(path=invalid_path):
                route = copy.deepcopy(original)
                route["path"] = invalid_path
                self.assertFalse(self.route_document_is_valid(route))

    def test_route_alias_uses_the_same_stable_path_syntax(self) -> None:
        original = self.documents["routes"]["routes"][0]
        for invalid_alias in ("/legacy path", "/legacy\npath", "/legacy\n", "/旧", "/%6cegacy"):
            with self.subTest(alias=invalid_alias):
                route = copy.deepcopy(original)
                route["aliases"] = [invalid_alias]
                self.assertFalse(self.route_document_is_valid(route))

    def test_route_contract_requires_canonical_routes(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        route["canonical"] = False
        self.assertFalse(self.route_document_is_valid(route))

    def test_unsupported_fixed_authentication_return_is_rejected(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        route["authenticationReturn"] = "fixed-route"
        self.assertFalse(self.route_document_is_valid(route))

    def test_required_authentication_requires_same_route_return(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][1])
        route["authenticationReturn"] = "not-applicable"
        self.assertFalse(self.route_document_is_valid(route))

    def test_no_authentication_requires_not_applicable_return(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        route["authentication"] = "none"
        route["authenticationReturn"] = "same-route"
        self.assertFalse(self.route_document_is_valid(route))
        route["authenticationReturn"] = "not-applicable"
        self.assertTrue(self.route_document_is_valid(route))

    def test_optional_authentication_allows_both_return_policies(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][2])
        for policy in ("same-route", "not-applicable"):
            with self.subTest(policy=policy):
                route["authenticationReturn"] = policy
                self.assertTrue(self.route_document_is_valid(route))


if __name__ == "__main__":
    unittest.main()
