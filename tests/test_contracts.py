from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class ContractValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)
        self.validators = {
            name: Draft202012Validator(validate_contracts.load_json(ROOT / schema_path))
            for name, (_, schema_path) in validate_contracts.CONTRACT_SCHEMAS.items()
        }
        self.route_validator = self.validators["routes"]

    def route_document_is_valid(self, route: dict[str, object]) -> bool:
        document = {
            "$schema": "../schemas/routes.schema.json",
            "schemaVersion": 1,
            "routes": [route],
        }
        return self.route_validator.is_valid(document)

    @staticmethod
    def set_nested(document: Any, path: tuple[str | int, ...], value: Any) -> None:
        target = document
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value

    def test_repository_contracts_are_valid(self) -> None:
        self.assertEqual([], validate_contracts.validate_repository(ROOT))

    def test_duplicate_json_object_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
            shutil.copytree(ROOT / "schemas", temporary_root / "schemas")
            duplicate_contract = (
                '{"$schema":"../schemas/routes.schema.json",'
                '"schemaVersion":1,"schemaVersion":1,"routes":[]}'
            )
            (temporary_root / "contracts/routes.json").write_text(
                duplicate_contract,
                encoding="utf-8",
            )
            errors = validate_contracts.validate_repository(temporary_root)
        self.assertTrue(any("duplicate object key 'schemaVersion'" in error for error in errors))

    def test_non_standard_json_numeric_constants_are_rejected(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    temporary_root = Path(temporary_directory)
                    shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
                    shutil.copytree(ROOT / "schemas", temporary_root / "schemas")
                    schema_path = temporary_root / "schemas/viewports.schema.json"
                    schema_text = schema_path.read_text(encoding="utf-8")
                    schema_path.write_text(
                        schema_text.replace('"minimum": 0', f'"minimum": {constant}', 1),
                        encoding="utf-8",
                    )
                    errors = validate_contracts.validate_repository(temporary_root)
                self.assertTrue(
                    any(
                        f"non-standard JSON numeric constant {constant!r}" in error
                        for error in errors
                    )
                )

    def test_identifier_fields_reject_terminal_newlines(self) -> None:
        cases = (
            ("surfaces", ("surfaces", 0, "id"), "public\n"),
            ("surfaces", ("surfaces", 0, "audiences", 0), "anonymous\n"),
            ("surfaces", ("surfaces", 1, "authorization", "roles", 0), "application-user\n"),
            ("surfaces", ("surfaces", 0, "dataClassifications", 0), "public\n"),
            ("surfaces", ("surfaces", 0, "startupDependencies"), ["application\n"]),
            ("routes", ("routes", 0, "id"), "home\n"),
            ("routes", ("routes", 0, "surface"), "public\n"),
            ("routes", ("routes", 0, "states", 0), "loading\n"),
            ("ui_states", ("states", 0, "id"), "loading\n"),
            ("ui_states", ("states", 1, "recoveryActions", 0), "create\n"),
            ("viewports", ("viewports", 0, "id"), "compact\n"),
        )
        for contract_name, path, invalid_value in cases:
            with self.subTest(contract=contract_name, path=path):
                document = copy.deepcopy(self.documents[contract_name])
                self.set_nested(document, path, invalid_value)
                self.assertFalse(self.validators[contract_name].is_valid(document))

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

    def test_public_authorization_must_not_require_authentication(self) -> None:
        documents = copy.deepcopy(self.documents)
        surface = documents["surfaces"]["surfaces"][0]
        route = documents["routes"]["routes"][0]
        surface["authentication"] = "required"
        route["authentication"] = "required"
        route["authenticationReturn"] = "same-route"
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("public authorization must not require authentication" in error for error in errors))

    def test_unsupported_policy_authorization_is_rejected(self) -> None:
        document = copy.deepcopy(self.documents["surfaces"])
        document["surfaces"][1]["authorization"] = {"mode": "policy", "roles": []}
        self.assertFalse(self.validators["surfaces"].is_valid(document))

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

    def test_viewport_breakpoints_must_be_strictly_increasing(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["viewports"]["viewports"][1]["minWidthPx"] = 0
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("viewport breakpoints must be strictly increasing" in error for error in errors))

    def test_viewport_upper_bound_is_derived_not_declared(self) -> None:
        document = copy.deepcopy(self.documents["viewports"])
        document["viewports"][0]["maxWidthPx"] = 767
        self.assertFalse(self.validators["viewports"].is_valid(document))

    def test_input_capabilities_are_global_not_breakpoint_specific(self) -> None:
        document = copy.deepcopy(self.documents["viewports"])
        document["viewports"][0]["interactionModes"] = ["pointer"]
        self.assertFalse(self.validators["viewports"].is_valid(document))

        document = copy.deepcopy(self.documents["viewports"])
        del document["inputCapabilities"]
        self.assertFalse(self.validators["viewports"].is_valid(document))

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

    def test_canonical_routes_require_document_titles(self) -> None:
        route = copy.deepcopy(self.documents["routes"]["routes"][0])
        route["accessibility"]["documentTitleRequired"] = False
        self.assertFalse(self.route_document_is_valid(route))

    def test_focus_targets_require_non_whitespace_content(self) -> None:
        original = self.documents["routes"]["routes"][0]
        for invalid_target in (" ", "\n", "\t", " \r\n\t"):
            with self.subTest(focus_target=repr(invalid_target)):
                route = copy.deepcopy(original)
                route["accessibility"]["focusTarget"] = invalid_target
                self.assertFalse(self.route_document_is_valid(route))

        route = copy.deepcopy(original)
        route["accessibility"]["focusTarget"] = "  #main-content  "
        self.assertTrue(self.route_document_is_valid(route))

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
