from __future__ import annotations

import copy
import http.client
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import test_webapp_productization_acceptance as product_helpers


ROOT = Path(__file__).resolve().parents[1]
REDIRECT_FIXTURE = ROOT / "tests" / "fixtures" / "webapp_auth" / "redirect_app.py"
FOUNDATION_COMPONENT = ROOT / "components" / "foundation.web" / "component.json"
MIGRATION = ROOT / "components" / "foundation.web" / "files" / "docs" / "migrations" / "routes-v3-to-v4.md"


class RoutesV3AccessFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._temp_dir = tempfile.TemporaryDirectory()
        helper = cls(
            methodName="test_explicit_access_fixture_binds_render_state_targets"
        )
        try:
            cls.target = helper.materialize_target(Path(cls._temp_dir.name))
        except BaseException:
            cls._temp_dir.cleanup()
            raise
        cls._baseline_contracts = {
            name: helper.load_json(cls.target / "contracts" / name)
            for name in ("routes.json", "application-routes.json", "surfaces.json", "ui-states.json")
        }

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._temp_dir.cleanup()
        finally:
            super().tearDownClass()

    def setUp(self) -> None:
        self.reset_shared_target()

    def reset_shared_target(self) -> None:
        for name, document in self._baseline_contracts.items():
            self.write_json(self.target / "contracts" / name, document)

    def helper(self) -> product_helpers.WebappProductizationAcceptanceTests:
        return product_helpers.WebappProductizationAcceptanceTests(
            methodName="test_composer_generated_webapp_reaches_revision_bound_product_release"
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_route_documents(self, target: Path, routes: dict) -> None:
        behavior_fields = {
            "surface",
            "authentication",
            "historyBehavior",
            "authenticationReturn",
            "accessFailures",
            "states",
        }
        shared_excluded_fields = behavior_fields | {"routeId"}
        shared_routes = []
        application_routes = []
        for route in routes["routes"]:
            shared_routes.append(
                {
                    key: value
                    for key, value in route.items()
                    if key not in shared_excluded_fields
                }
            )
            application_routes.append(
                {
                    "routeId": route["id"],
                    **{key: route[key] for key in behavior_fields},
                }
            )
        self.write_json(
            target / "contracts/routes.json",
            {
                "$schema": "../schemas/routes.schema.json",
                "schemaVersion": 5,
                "routes": shared_routes,
            },
        )
        self.write_json(
            target / "contracts/application-routes.json",
            {
                "$schema": "../schemas/application-routes.schema.json",
                "schemaVersion": 1,
                "routes": application_routes,
            },
        )

    def load_routes_with_behavior(self, target: Path) -> dict:
        routes = self.load_json(target / "contracts/routes.json")
        application = self.load_json(target / "contracts/application-routes.json")
        behavior_by_id = {item["routeId"]: item for item in application["routes"]}
        return {
            "$schema": routes["$schema"],
            "schemaVersion": routes["schemaVersion"],
            "routes": [
                {
                    **route,
                    **behavior_by_id[route["id"]],
                    "id": route["id"],
                }
                for route in routes["routes"]
            ],
        }

    def configure_access_fixture(self, target: Path) -> None:
        self.write_json(
            target / "contracts/surfaces.json",
            {
                "$schema": "../schemas/surfaces.schema.json",
                "schemaVersion": 2,
                "surfaces": [
                    {
                        "id": "primary",
                        "title": "Public surface",
                        "purpose": "Exercise public-route access-failure invariants.",
                        "audiences": ["anonymous"],
                        "authentication": "none",
                        "authorization": {"mode": "public", "roles": []},
                        "dataClassifications": ["public"],
                        "stability": "experimental",
                        "surfaceDependencies": [],
                        "diagnostic": False,
                    },
                    {
                        "id": "application",
                        "title": "Protected application surface",
                        "purpose": "Exercise authentication and role access failures.",
                        "audiences": ["authenticated-user"],
                        "authentication": "required",
                        "authorization": {
                            "mode": "role",
                            "roles": ["application-user"],
                        },
                        "dataClassifications": ["internal"],
                        "stability": "experimental",
                        "surfaceDependencies": [],
                        "diagnostic": False,
                    },
                ],
            },
        )
        self.write_json(
            target / "contracts/ui-states.json",
            {
                "$schema": "../schemas/ui-states.schema.json",
                "schemaVersion": 2,
                "states": [
                    {
                        "id": "ready",
                        "scope": "route",
                        "category": "content",
                        "description": "Route content is ready.",
                        "recoveryActions": [],
                        "announcement": "none",
                        "focusStrategy": "preserve",
                    },
                    {
                        "id": "loading",
                        "scope": "route",
                        "category": "progress",
                        "description": "Protected content is loading.",
                        "recoveryActions": [],
                        "announcement": "polite",
                        "focusStrategy": "preserve",
                    },
                    {
                        "id": "unauthorized",
                        "scope": "route",
                        "category": "access",
                        "description": "Authentication is required.",
                        "recoveryActions": [],
                        "announcement": "assertive",
                        "focusStrategy": "main-heading",
                    },
                    {
                        "id": "forbidden",
                        "scope": "route",
                        "category": "access",
                        "description": "The authenticated principal lacks the required role.",
                        "recoveryActions": [],
                        "announcement": "assertive",
                        "focusStrategy": "main-heading",
                    },
                    {
                        "id": "fatal-error",
                        "scope": "global",
                        "category": "error",
                        "description": "A global fatal error is visible.",
                        "recoveryActions": [],
                        "announcement": "assertive",
                        "focusStrategy": "main-heading",
                    },
                ],
            },
        )
        self.write_json(
            target / "contracts/routes.json",
            {
                "$schema": "../schemas/routes.schema.json",
                "schemaVersion": 3,
                "routes": [
                    {
                        "id": "home",
                        "path": "/",
                        "surface": "primary",
                        "canonical": True,
                        "aliases": [],
                        "authentication": "none",
                        "deepLink": True,
                        "historyBehavior": "replace",
                        "authenticationReturn": "not-applicable",
                        "accessFailures": {
                            "unauthenticated": {"behavior": "not-applicable"},
                            "forbidden": {"behavior": "not-applicable"},
                        },
                        "states": ["ready"],
                        "accessibility": {
                            "documentTitleRequired": True,
                            "focusTarget": "main-heading",
                        },
                    },
                    {
                        "id": "application-home",
                        "path": "/app",
                        "surface": "application",
                        "canonical": True,
                        "aliases": [],
                        "authentication": "required",
                        "deepLink": True,
                        "historyBehavior": "push",
                        "authenticationReturn": "same-route",
                        "accessFailures": {
                            "unauthenticated": {
                                "behavior": "render-state",
                                "stateId": "unauthorized",
                            },
                            "forbidden": {
                                "behavior": "render-state",
                                "stateId": "forbidden",
                            },
                        },
                        "states": [
                            "ready",
                            "loading",
                            "unauthorized",
                            "forbidden",
                        ],
                        "accessibility": {
                            "documentTitleRequired": True,
                            "focusTarget": "main-heading",
                        },
                    },
                ],
            },
        )
        self.write_route_documents(target, self.load_json(target / "contracts/routes.json"))

    def materialize_target(self, root: Path) -> Path:
        helper = self.helper()
        target = root / "consumer"
        config = root / "composition.json"
        helper.write_webapp_config(config)
        result, payload = helper.run_composer(
            "apply",
            "--config",
            str(config),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)
        self.configure_access_fixture(target)
        return target

    def validate_contracts(self, target: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/validate_contracts.py"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def route(self, routes: dict, route_id: str) -> dict:
        return next(route for route in routes["routes"] if route["id"] == route_id)

    def assert_invalid_mutation(
        self,
        mutate: Callable[[dict, dict, dict], None],
        *,
        expected: str | None = None,
    ) -> None:
        self.reset_shared_target()
        routes_path = self.target / "contracts/routes.json"
        surfaces_path = self.target / "contracts/surfaces.json"
        states_path = self.target / "contracts/ui-states.json"
        routes = self.load_routes_with_behavior(self.target)
        surfaces = self.load_json(surfaces_path)
        states = self.load_json(states_path)
        mutate(routes, surfaces, states)
        self.write_route_documents(self.target, routes)
        self.write_json(surfaces_path, surfaces)
        self.write_json(states_path, states)
        result = self.validate_contracts(self.target)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        if expected is not None:
            self.assertIn(expected, output)

    def load_redirect_app(self, target: Path):
        product = target / "product"
        product.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, product, ignore_errors=True)
        path = product / "redirect_app.py"
        path.write_text(REDIRECT_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("routes_v3_redirect_fixture", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec is not None else None)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def request(
        self,
        port: int,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            body = response.read().decode("utf-8")
            response_headers = {key: value for key, value in response.getheaders()}
            return response.status, response_headers, body
        finally:
            connection.close()

    def test_explicit_access_fixture_binds_render_state_targets(self) -> None:
        routes = self.load_routes_with_behavior(self.target)
        self.assertEqual(routes["schemaVersion"], 5)
        application = self.route(routes, "application-home")
        self.assertEqual(
            application["accessFailures"],
            {
                "unauthenticated": {
                    "behavior": "render-state",
                    "stateId": "unauthorized",
                },
                "forbidden": {
                    "behavior": "render-state",
                    "stateId": "forbidden",
                },
            },
        )
        valid = self.validate_contracts(self.target)
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

    def test_redirect_binds_semantic_route_without_prescribing_return_transport(self) -> None:
        surfaces_path = self.target / "contracts/surfaces.json"
        routes_path = self.target / "contracts/routes.json"
        surfaces = self.load_json(surfaces_path)
        routes = self.load_routes_with_behavior(self.target)

        surfaces["surfaces"].append(
            {
                "id": "sign-in",
                "title": "Sign-in surface",
                "purpose": "Accept authentication before returning to a protected route.",
                "audiences": ["anonymous", "authenticated-user"],
                "authentication": "none",
                "authorization": {"mode": "public", "roles": []},
                "dataClassifications": ["public"],
                "stability": "stable",
                "surfaceDependencies": [],
                "diagnostic": False,
            }
        )
        application = self.route(routes, "application-home")
        application["accessFailures"]["unauthenticated"] = {
            "behavior": "redirect",
            "routeId": "sign-in",
        }
        routes["routes"].append(
            {
                "id": "sign-in",
                "path": "/sign-in",
                "surface": "sign-in",
                "canonical": True,
                "aliases": [],
                "authentication": "none",
                "deepLink": True,
                "historyBehavior": "replace",
                "authenticationReturn": "not-applicable",
                "accessFailures": {
                    "unauthenticated": {"behavior": "not-applicable"},
                    "forbidden": {"behavior": "not-applicable"},
                },
                "states": ["ready"],
                "accessibility": {
                    "documentTitleRequired": True,
                    "focusTarget": "main-heading",
                },
            }
        )
        self.write_json(surfaces_path, surfaces)
        self.write_route_documents(self.target, routes)

        valid = self.validate_contracts(self.target)
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
        target_route = self.route(
            routes, application["accessFailures"]["unauthenticated"]["routeId"]
        )
        self.assertEqual(target_route["path"], "/sign-in")
        self.assertNotIn("returnTo", json.dumps(application, sort_keys=True))

        redirect_app = self.load_redirect_app(self.target)
        server = redirect_app.make_server()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            status, headers, _ = self.request(port, "/app")
            self.assertEqual(status, 302)
            location = headers["Location"]
            self.assertEqual(urlsplit(location).path, target_route["path"])
            self.assertEqual(location, "/sign-in?returnTo=%2Fapp")

            status, _, body = self.request(port, location)
            self.assertEqual(status, 200)
            self.assertEqual(body.strip(), "sign-in:return-to=/app")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

        application["accessFailures"]["unauthenticated"]["returnTo"] = "same-route"
        self.write_route_documents(self.target, routes)
        invalid = self.validate_contracts(self.target)
        self.assertNotEqual(invalid.returncode, 0, invalid.stdout + invalid.stderr)

    def test_rejects_unknown_render_state_target(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            self.route(routes, "application-home")["accessFailures"]["unauthenticated"] = {
                "behavior": "render-state",
                "stateId": "missing-state",
            }

        self.assert_invalid_mutation(mutate, expected="unknown UI state missing-state")

    def test_rejects_non_access_render_state_target(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            self.route(routes, "application-home")["accessFailures"]["unauthenticated"] = {
                "behavior": "render-state",
                "stateId": "loading",
            }

        self.assert_invalid_mutation(mutate, expected="must have category access")

    def test_rejects_global_render_state_target(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            application = self.route(routes, "application-home")
            application["accessFailures"]["unauthenticated"] = {
                "behavior": "render-state",
                "stateId": "fatal-error",
            }
            application["states"].append("fatal-error")

        self.assert_invalid_mutation(mutate, expected="must be route-scoped")

    def test_rejects_render_state_not_declared_by_route(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            application = self.route(routes, "application-home")
            application["states"].remove("unauthorized")

        self.assert_invalid_mutation(
            mutate,
            expected="render-state target unauthorized must be declared by the route",
        )

    def test_rejects_unknown_redirect_route(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            self.route(routes, "application-home")["accessFailures"]["unauthenticated"] = {
                "behavior": "redirect",
                "routeId": "missing-route",
            }

        self.assert_invalid_mutation(mutate, expected="unknown redirect route missing-route")

    def test_rejects_self_redirect(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            self.route(routes, "application-home")["accessFailures"]["unauthenticated"] = {
                "behavior": "redirect",
                "routeId": "application-home",
            }

        self.assert_invalid_mutation(
            mutate, expected="must not redirect to the same route"
        )

    def test_rejects_unauthenticated_redirect_to_auth_required_route(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            application = self.route(routes, "application-home")
            account = copy.deepcopy(application)
            account["id"] = "account"
            account["path"] = "/account"
            routes["routes"].append(account)
            application["accessFailures"]["unauthenticated"] = {
                "behavior": "redirect",
                "routeId": "account",
            }

        self.assert_invalid_mutation(
            mutate,
            expected="unauthenticated redirect target account must not require authentication",
        )

    def test_public_route_rejects_applicable_unauthenticated_failure(self) -> None:
        for behavior in (
            {"behavior": "render-state", "stateId": "unauthorized"},
            {"behavior": "redirect", "routeId": "application-home"},
        ):
            with self.subTest(behavior=behavior["behavior"]):

                def mutate(
                    routes: dict,
                    _surfaces: dict,
                    _states: dict,
                    failure: dict = behavior,
                ) -> None:
                    home = self.route(routes, "home")
                    home["accessFailures"]["unauthenticated"] = failure
                    if failure["behavior"] == "render-state":
                        home["states"].append("unauthorized")

                self.assert_invalid_mutation(mutate)

    def test_non_role_surface_rejects_applicable_forbidden_failure(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            home = self.route(routes, "home")
            home["accessFailures"]["forbidden"] = {
                "behavior": "render-state",
                "stateId": "unauthorized",
            }
            home["states"].append("unauthorized")

        self.assert_invalid_mutation(
            mutate,
            expected="public authorization requires forbidden access failure not-applicable",
        )

    def test_current_component_preserves_routes_v3_history_and_migration(self) -> None:
        component = self.load_json(FOUNDATION_COMPONENT)
        registration = next(
            item
            for item in component["contract_registrations"]
            if item["id"] == "routes"
        )
        self.assertEqual(registration["document_schema_version"], 5)
        self.assertEqual(
            registration["version_history"],
            [
                {"version": 1, "change_type": "initial"},
                {
                    "version": 2,
                    "change_type": "breaking",
                    "migration": "docs/migrations/routes-v1-to-v2.md",
                },
                {
                    "version": 3,
                    "change_type": "breaking",
                    "migration": "docs/migrations/routes-v2-to-v3.md",
                },
                {
                    "version": 4,
                    "change_type": "breaking",
                    "migration": "docs/migrations/routes-v3-to-v4.md",
                },
                {"version": 5, "change_type": "additive", "migration": "docs/migrations/routes-v4-to-v5.md"},
            ],
        )
        material_pairs = {
            (item.get("source"), item["destination"])
            for item in component["materials"]
        }
        self.assertIn(
            (
                "files/docs/migrations/routes-v3-to-v4.md",
                "docs/migrations/routes-v3-to-v4.md",
            ),
            material_pairs,
        )
        self.assertIn(
            (
                "files/schemas/routes.schema.json",
                "schemas/routes.schema.json",
            ),
            material_pairs,
        )
        migration = MIGRATION.read_text(encoding="utf-8")
        self.assertIn(
            "Routes v4 is owned by `foundation.web`", migration
        )
        self.assertIn("application-routes.json", migration)

    def test_composer_materializes_routes_v3_and_v3_validator(self) -> None:
        routes = self.load_routes_with_behavior(self.target)
        self.assertEqual(routes["schemaVersion"], 5)
        validator_source = (
            self.target / "scripts/validate_contracts_impl.py"
        ).read_text(encoding="utf-8")
        self.assertIn("unknown redirect route", validator_source)
        self.assertTrue((self.target / "docs/migrations/routes-v3-to-v4.md").is_file())
        valid = self.validate_contracts(self.target)
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)


if __name__ == "__main__":
    unittest.main()
