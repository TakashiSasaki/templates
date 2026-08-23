from __future__ import annotations

import http.client
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import test_webapp_productization_acceptance as product_helpers


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "webapp_auth" / "redirect_app.py"


class RoutesV2RedirectExpressivenessTests(unittest.TestCase):
    def helper(self) -> product_helpers.WebappProductizationAcceptanceTests:
        return product_helpers.WebappProductizationAcceptanceTests(
            methodName="test_composer_generated_webapp_reaches_revision_bound_product_release"
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def materialize_redirect_contract(self, root: Path) -> Path:
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

        surfaces_path = target / "contracts/surfaces.json"
        surfaces = json.loads(surfaces_path.read_text(encoding="utf-8"))
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
                "startupDependencies": [],
                "diagnostic": False,
            }
        )
        self.write_json(surfaces_path, surfaces)

        routes_path = target / "contracts/routes.json"
        routes = json.loads(routes_path.read_text(encoding="utf-8"))
        application = next(
            route for route in routes["routes"] if route["id"] == "application-home"
        )
        application["accessFailures"]["unauthenticated"] = "redirect"
        application["states"].remove("unauthorized")
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
                    "unauthenticated": "not-applicable",
                    "forbidden": "not-applicable",
                },
                "states": ["loading", "populated", "recoverable-error"],
                "accessibility": {
                    "documentTitleRequired": True,
                    "focusTarget": "main-heading",
                },
            }
        )
        self.write_json(routes_path, routes)

        states_path = target / "contracts/ui-states.json"
        states = json.loads(states_path.read_text(encoding="utf-8"))
        states["states"] = [
            state for state in states["states"] if state["id"] != "unauthorized"
        ]
        self.write_json(states_path, states)

        product = target / "product"
        product.mkdir()
        (product / "redirect_app.py").write_text(
            FIXTURE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return target

    def validate_contracts(self, target: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/validate_contracts.py"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def load_redirect_app(self, target: Path):
        path = target / "product/redirect_app.py"
        spec = importlib.util.spec_from_file_location("redirect_gap_fixture", path)
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

    def test_v2_validates_redirect_behavior_but_cannot_name_its_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_redirect_contract(Path(temp_dir))
            valid = self.validate_contracts(target)
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

            routes_path = target / "contracts/routes.json"
            routes = json.loads(routes_path.read_text(encoding="utf-8"))
            application = next(
                route
                for route in routes["routes"]
                if route["id"] == "application-home"
            )
            self.assertEqual(
                application["accessFailures"]["unauthenticated"], "redirect"
            )
            serialized_application = json.dumps(application, sort_keys=True)
            self.assertNotIn("sign-in", serialized_application)
            self.assertNotIn("returnTo", serialized_application)

            redirect_app = self.load_redirect_app(target)
            server = redirect_app.make_server()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            try:
                status, headers, _ = self.request(port, "/app")
                self.assertEqual(status, 302)
                self.assertEqual(headers["Location"], "/sign-in?returnTo=%2Fapp")

                status, _, body = self.request(port, headers["Location"])
                self.assertEqual(status, 200)
                self.assertEqual(body.strip(), "sign-in:return-to=/app")

                status, _, body = self.request(
                    port,
                    "/app",
                    headers={"X-User": "alice", "X-Roles": "application-user"},
                )
                self.assertEqual((status, body.strip()), (200, "application:populated"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())

            application["accessFailures"]["unauthenticated"] = {
                "behavior": "redirect",
                "routeId": "sign-in",
                "returnTo": "same-route",
            }
            self.write_json(routes_path, routes)
            invalid = self.validate_contracts(target)
            self.assertNotEqual(invalid.returncode, 0)


if __name__ == "__main__":
    unittest.main()
