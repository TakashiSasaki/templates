from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
WEBAPP_COMPONENT = ROOT / "components" / "artifact.webapp-core" / "component.json"
ROUTES_SCHEMA = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "schemas"
    / "routes.schema.json"
)
ROUTES_VALIDATOR = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "scripts"
    / "validate_routes.py"
)
ROUTES_DOCUMENT = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "contracts"
    / "routes.json"
)
SURFACES_DOCUMENT = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "contracts"
    / "surfaces.json"
)
STATES_DOCUMENT = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "contracts"
    / "ui-states.json"
)


class RoutesV3AccessFailureTests(unittest.TestCase):
    def run_python(
        self, cwd: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def route(self, routes: dict, route_id: str) -> dict:
        return next(route for route in routes["routes"] if route["id"] == route_id)

    def state(self, states: dict, state_id: str) -> dict:
        return next(state for state in states["states"] if state["id"] == state_id)

    def materialized_fixture(
        self,
        root: Path,
        *,
        surfaces: dict | None = None,
        routes: dict | None = None,
        states: dict | None = None,
    ) -> Path:
        target = root / "consumer"
        target.mkdir()
        (target / "contracts").mkdir()
        (target / "schemas").mkdir()
        (target / "scripts").mkdir()
        (target / "schemas/routes.schema.json").write_bytes(ROUTES_SCHEMA.read_bytes())
        (target / "scripts/validate_routes.py").write_bytes(ROUTES_VALIDATOR.read_bytes())
        self.write_json(
            target / "contracts/surfaces.json",
            surfaces if surfaces is not None else self.load_json(SURFACES_DOCUMENT),
        )
        self.write_json(
            target / "contracts/routes.json",
            routes if routes is not None else self.load_json(ROUTES_DOCUMENT),
        )
        self.write_json(
            target / "contracts/ui-states.json",
            states if states is not None else self.load_json(STATES_DOCUMENT),
        )
        return target

    def run_validator(self, target: Path) -> subprocess.CompletedProcess[str]:
        return self.run_python(target, "scripts/validate_routes.py")

    def assert_invalid_mutation(
        self,
        mutate,
        *,
        expected: str | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            routes = self.load_json(ROUTES_DOCUMENT)
            surfaces = self.load_json(SURFACES_DOCUMENT)
            states = self.load_json(STATES_DOCUMENT)
            mutate(routes, surfaces, states)
            target = self.materialized_fixture(
                Path(temp_dir), surfaces=surfaces, routes=routes, states=states
            )
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            if expected is not None:
                self.assertIn(expected, result.stderr)

    def test_schema_is_v3_and_requires_explicit_access_failures(self) -> None:
        schema = self.load_json(ROUTES_SCHEMA)
        Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], 3)
        route_schema = schema["$defs"]["route"]
        self.assertIn("accessFailures", route_schema["required"])
        self.assertEqual(
            route_schema["properties"]["accessFailures"]["required"],
            ["unauthenticated", "forbidden"],
        )

    def test_canonical_routes_are_schema_and_semantically_valid(self) -> None:
        routes = self.load_json(ROUTES_DOCUMENT)
        schema = self.load_json(ROUTES_SCHEMA)
        errors = list(Draft202012Validator(schema).iter_errors(routes))
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialized_fixture(Path(temp_dir), routes=routes)
            result = self.run_validator(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_composer_materializes_routes_v3_and_v3_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = root / "composition.json"
            target = root / "consumer"
            self.write_json(
                config,
                {
                    "schema_version": 1,
                    "recipe": "webapp",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
            )
            result = self.run_python(
                ROOT,
                str(COMPOSER),
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            routes = self.load_json(target / "contracts/routes.json")
            self.assertEqual(routes["schemaVersion"], 3)
            result = self.run_python(target, "scripts/validate_routes.py")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_public_route_rejects_applicable_unauthenticated_failure(self) -> None:
        for behavior in (
            {"behavior": "redirect", "routeId": "home"},
            {"behavior": "render-state", "stateId": "unauthorized"},
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
        component = self.load_json(WEBAPP_COMPONENT)
        self.assertEqual(component["version"], 8)
        registration = next(
            item
            for item in component["contract_registrations"]
            if item["id"] == "routes"
        )
        self.assertEqual(registration["document_schema_version"], 3)
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
            ],
        )
        material_pairs = {
            (item.get("source"), item.get("destination"))
            for item in component["materials"]
        }
        self.assertIn(
            ("files/docs/migrations/routes-v1-to-v2.md", "docs/migrations/routes-v1-to-v2.md"),
            material_pairs,
        )
        self.assertIn(
            ("files/docs/migrations/routes-v2-to-v3.md", "docs/migrations/routes-v2-to-v3.md"),
            material_pairs,
        )

    def test_redirect_binds_semantic_route_without_prescribing_return_transport(self) -> None:
        routes = self.load_json(ROUTES_DOCUMENT)
        surfaces = self.load_json(SURFACES_DOCUMENT)
        states = self.load_json(STATES_DOCUMENT)
        routes["routes"].append(
            {
                "id": "login",
                "surface": "primary",
                "path": "/login",
                "aliases": [],
                "canonical": False,
                "authentication": "none",
                "authenticationReturn": "not-applicable",
                "accessFailures": {
                    "unauthenticated": {"behavior": "not-applicable"},
                    "forbidden": {"behavior": "not-applicable"},
                },
                "states": ["ready"],
                "accessibility": {"focusTarget": "main-heading"},
                "documentTitle": "Login",
            }
        )
        primary = next(
            surface for surface in surfaces["surfaces"] if surface["id"] == "primary"
        )
        primary["authentication"] = "session-cookie"
        home = self.route(routes, "home")
        home["authentication"] = "required"
        home["authenticationReturn"] = "preserve-requested-route"
        home["accessFailures"]["unauthenticated"] = {
            "behavior": "redirect",
            "routeId": "login",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialized_fixture(
                Path(temp_dir), surfaces=surfaces, routes=routes, states=states
            )
            result = self.run_validator(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_self_redirect(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            home = self.route(routes, "home")
            home["accessFailures"]["unauthenticated"] = {
                "behavior": "redirect",
                "routeId": "home",
            }

        self.assert_invalid_mutation(mutate)

    def test_rejects_unknown_redirect_route(self) -> None:
        def mutate(routes: dict, _surfaces: dict, _states: dict) -> None:
            home = self.route(routes, "home")
            home["accessFailures"]["unauthenticated"] = {
                "behavior": "redirect",
                "routeId": "missing",
            }

        self.assert_invalid_mutation(mutate)

    def test_rejects_unauthenticated_redirect_to_auth_required_route(self) -> None:
        routes = self.load_json(ROUTES_DOCUMENT)
        surfaces = self.load_json(SURFACES_DOCUMENT)
        states = self.load_json(STATES_DOCUMENT)
        routes["routes"].append(
            {
                "id": "private-login",
                "surface": "primary",
                "path": "/private-login",
                "aliases": [],
                "canonical": False,
                "authentication": "required",
                "authenticationReturn": "not-applicable",
                "accessFailures": {
                    "unauthenticated": {"behavior": "not-applicable"},
                    "forbidden": {"behavior": "not-applicable"},
                },
                "states": ["ready"],
                "accessibility": {"focusTarget": "main-heading"},
                "documentTitle": "Private login",
            }
        )
        primary = next(
            surface for surface in surfaces["surfaces"] if surface["id"] == "primary"
        )
        primary["authentication"] = "session-cookie"
        home = self.route(routes, "home")
        home["authentication"] = "required"
        home["authenticationReturn"] = "preserve-requested-route"
        home["accessFailures"]["unauthenticated"] = {
            "behavior": "redirect",
            "routeId": "private-login",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialized_fixture(
                Path(temp_dir), surfaces=surfaces, routes=routes, states=states
            )
            result = self.run_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unauthenticated redirect route", result.stderr)

    def test_explicit_access_fixture_binds_render_state_targets(self) -> None:
        routes = self.load_json(ROUTES_DOCUMENT)
        surfaces = self.load_json(SURFACES_DOCUMENT)
        states = self.load_json(STATES_DOCUMENT)
        primary = next(
            surface for surface in surfaces["surfaces"] if surface["id"] == "primary"
        )
        primary["authentication"] = "session-cookie"
        primary["authorization"] = {"mode": "roles", "roles": ["reader"]}
        home = self.route(routes, "home")
        home["authentication"] = "required"
        home["authenticationReturn"] = "preserve-requested-route"
        home["accessFailures"]["unauthenticated"] = {
            "behavior": "render-state",
            "stateId": "unauthorized",
        }
        home["accessFailures"]["forbidden"] = {
            "behavior": "render-state",
            "stateId": "forbidden",
        }
        home["states"].extend(["unauthorized", "forbidden"])
        states["states"].extend(
            [
                {
                    "id": "unauthorized",
                    "scope": {"kind": "route", "routeId": "home"},
                    "category": "access",
                    "description": "Authentication is required.",
                    "focusStrategy": "main-heading",
                    "announcement": "assertive",
                },
                {
                    "id": "forbidden",
                    "scope": {"kind": "route", "routeId": "home"},
                    "category": "access",
                    "description": "The current role may not view this route.",
                    "focusStrategy": "main-heading",
                    "announcement": "assertive",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialized_fixture(
                Path(temp_dir), surfaces=surfaces, routes=routes, states=states
            )
            result = self.run_validator(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_global_render_state_target(self) -> None:
        def mutate(routes: dict, _surfaces: dict, states: dict) -> None:
            states["states"].append(
                {
                    "id": "unauthorized",
                    "scope": {"kind": "global"},
                    "category": "access",
                    "description": "Authentication is required.",
                    "focusStrategy": "preserve",
                    "announcement": "assertive",
                }
            )
            home = self.route(routes, "home")
            home["authentication"] = "required"
            home["accessFailures"]["unauthenticated"] = {
                "behavior": "render-state",
                "stateId": "unauthorized",
            }
            home["states"].append("unauthorized")

        self.assert_invalid_mutation(mutate, expected="must be scoped to route")

    def test_rejects_non_access_render_state_target(self) -> None:
        def mutate(routes: dict, _surfaces: dict, states: dict) -> None:
            states["states"].append(
                {
                    "id": "loading",
                    "scope": {"kind": "route", "routeId": "home"},
                    "category": "loading",
                    "description": "Loading.",
                    "focusStrategy": "preserve",
                    "announcement": "polite",
                }
            )
            home = self.route(routes, "home")
            home["authentication"] = "required"
            home["accessFailures"]["unauthenticated"] = {
                "behavior": "render-state",
                "stateId": "loading",
            }
            home["states"].append("loading")

        self.assert_invalid_mutation(mutate, expected="must use category access or error")

    def test_rejects_render_state_not_declared_by_route(self) -> None:
        def mutate(routes: dict, _surfaces: dict, states: dict) -> None:
            states["states"].append(
                {
                    "id": "unauthorized",
                    "scope": {"kind": "route", "routeId": "home"},
                    "category": "access",
                    "description": "Authentication is required.",
                    "focusStrategy": "preserve",
                    "announcement": "assertive",
                }
            )
            home = self.route(routes, "home")
            home["authentication"] = "required"
            home["accessFailures"]["unauthenticated"] = {
                "behavior": "render-state",
                "stateId": "unauthorized",
            }

        self.assert_invalid_mutation(
            mutate,
            expected="must also be declared in route states",
        )


if __name__ == "__main__":
    unittest.main()
