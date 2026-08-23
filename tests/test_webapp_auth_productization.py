from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_webapp_productization_acceptance as product_helpers


AUTH_PROOF_COMMAND = "python product/prove_auth_fixture.py"
AUTH_APP_TEMPLATE = r'''from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROLE_BY_PATH = {
    "/app": "application-user",
    "/admin": "admin",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def respond(self, status: int, body: str) -> None:
        payload = (body + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/":
            self.respond(200, "public:populated")
            return
        if path == "/status":
            self.respond(200, "status:populated")
            return
        if path not in ROLE_BY_PATH:
            self.respond(404, "not-found")
            return

        user = self.headers.get("X-User", "").strip()
        roles = {
            value.strip()
            for value in self.headers.get("X-Roles", "").split(",")
            if value.strip()
        }
        if not user:
            self.respond(401, "unauthorized")
            return

        required_role = ROLE_BY_PATH[path]
        if required_role not in roles and not ({allow_admin_without_role!r} and path == "/admin"):
            self.respond(403, "forbidden")
            return

        state = parse_qs(parsed.query).get("state", ["populated"])[0]
        if state == "loading":
            self.respond(200, path.removeprefix("/") + ":loading")
            return
        if state == "recoverable-error":
            self.respond(503, "recoverable-error")
            return
        if state != "populated":
            self.respond(400, "unsupported-state")
            return
        self.respond(200, path.removeprefix("/") + ":populated")


def make_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
'''

AUTH_PROOF_SCRIPT = r'''from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import auth_app

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("contracts", (sys.executable, "scripts/validate_contracts.py")),
    (
        "contract evolution",
        (
            sys.executable,
            ".template-composition/validators/validate_contract_evolution.py",
            ".",
        ),
    ),
    (
        "implementation evidence",
        (
            sys.executable,
            ".template-composition/validators/validate_implementation_evidence.py",
            ".",
        ),
    ),
    (
        "release execution",
        (
            sys.executable,
            ".template-composition/validators/validate_release_execution.py",
            ".",
        ),
    ),
    (
        "Webapp evidence coverage",
        (sys.executable, "scripts/validate_webapp_evidence.py"),
    ),
)

for label, command in CHECKS:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"{label} failed", file=sys.stderr)
        print(result.stdout, file=sys.stderr, end="")
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)

routes = {
    route["id"]: route
    for route in json.loads(
        (ROOT / "contracts/routes.json").read_text(encoding="utf-8")
    )["routes"]
}
surfaces = {
    surface["id"]: surface
    for surface in json.loads(
        (ROOT / "contracts/surfaces.json").read_text(encoding="utf-8")
    )["surfaces"]
}
for route_id, surface_id, required_role in (
    ("application-home", "application", "application-user"),
    ("admin", "admin", "admin"),
):
    route = routes[route_id]
    surface = surfaces[surface_id]
    assert route["authentication"] == "required"
    assert route["accessFailures"] == {
        "unauthenticated": "render-state",
        "forbidden": "render-state",
    }
    assert {"loading", "populated", "recoverable-error", "unauthorized", "forbidden"} <= set(route["states"])
    assert surface["authorization"] == {"mode": "role", "roles": [required_role]}

server = auth_app.make_server()
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_address[1]}"


def request(path: str, *, user: str | None = None, roles: tuple[str, ...] = ()) -> tuple[int, str]:
    headers = {}
    if user is not None:
        headers["X-User"] = user
    if roles:
        headers["X-Roles"] = ",".join(roles)
    try:
        with urlopen(Request(base + path, headers=headers), timeout=5) as response:
            return response.status, response.read().decode("utf-8").strip()
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8").strip()


try:
    assert request("/") == (200, "public:populated")
    assert request("/app") == (401, "unauthorized")
    assert request("/app", user="alice", roles=("application-user",)) == (200, "app:populated")
    assert request("/app", user="alice", roles=("admin",)) == (403, "forbidden")
    assert request("/admin") == (401, "unauthorized")
    assert request("/admin", user="alice", roles=("application-user",)) == (403, "forbidden")
    assert request("/admin", user="alice", roles=("admin",)) == (200, "admin:populated")
    assert request("/app?state=loading", user="alice", roles=("application-user",)) == (200, "app:loading")
    assert request("/app?state=recoverable-error", user="alice", roles=("application-user",)) == (503, "recoverable-error")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

print("Webapp auth product proof: route access and UI-state behavior passed")
'''


class WebappAuthenticationProductizationTests(unittest.TestCase):
    def helper(self) -> product_helpers.WebappProductizationAcceptanceTests:
        return product_helpers.WebappProductizationAcceptanceTests(
            methodName="test_composer_generated_webapp_reaches_revision_bound_product_release"
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def add_admin_contracts(self, target: Path) -> None:
        surfaces_path = target / "contracts/surfaces.json"
        surfaces = json.loads(surfaces_path.read_text(encoding="utf-8"))
        surfaces["surfaces"].append(
            {
                "id": "admin",
                "title": "Administrative surface",
                "purpose": "Provide role-restricted administrative operations.",
                "audiences": ["operator"],
                "authentication": "required",
                "authorization": {"mode": "role", "roles": ["admin"]},
                "dataClassifications": ["internal"],
                "stability": "experimental",
                "startupDependencies": [],
                "diagnostic": false,
            }
        )
        self.write_json(surfaces_path, surfaces)

        routes_path = target / "contracts/routes.json"
        routes = json.loads(routes_path.read_text(encoding="utf-8"))
        routes["routes"].append(
            {
                "id": "admin",
                "path": "/admin",
                "surface": "admin",
                "canonical": True,
                "aliases": [],
                "authentication": "required",
                "deepLink": True,
                "historyBehavior": "push",
                "authenticationReturn": "same-route",
                "accessFailures": {
                    "unauthenticated": "render-state",
                    "forbidden": "render-state",
                },
                "states": [
                    "loading",
                    "populated",
                    "recoverable-error",
                    "unauthorized",
                    "forbidden",
                ],
                "accessibility": {
                    "documentTitleRequired": True,
                    "focusTarget": "main-heading",
                },
            }
        )
        self.write_json(routes_path, routes)

    def scaffold_product_evidence(self, target: Path) -> list[dict]:
        scaffold = subprocess.run(
            [sys.executable, "scripts/scaffold_webapp_evidence.py"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(scaffold.returncode, 0, scaffold.stdout + scaffold.stderr)
        worklist = json.loads(scaffold.stdout)
        self.assertEqual(worklist["format"], "webapp-implementation-evidence-worklist")
        self.assertEqual(worklist["recordCount"], len(worklist["records"]))
        targets = [record["target"] for record in worklist["records"]]
        self.assertIn(
            {
                "kind": "contract-item",
                "contractId": "surfaces",
                "itemKind": "surface",
                "itemId": "admin",
            },
            targets,
        )
        self.assertIn(
            {
                "kind": "contract-item",
                "contractId": "routes",
                "itemKind": "route",
                "itemId": "admin",
            },
            targets,
        )

        records: list[dict] = []
        for skeleton in worklist["records"]:
            identifier = skeleton["id"]
            records.append(
                {
                    "id": identifier,
                    "target": skeleton["target"],
                    "implementationBoundary": {
                        "status": "verified",
                        "description": "The executable auth fixture implements this generated Webapp target.",
                        "locator": "product/auth_app.py",
                    },
                    "positiveEvidence": [
                        {
                            "id": f"{identifier}-positive",
                            "status": "verified",
                            "kind": "integration-test",
                            "description": "The auth proof exercises the target through contract and HTTP behavior checks.",
                            "locator": "product/prove_auth_fixture.py",
                            "commandId": "auth-product-proof",
                            "expectedResult": "The declared route, state, access, and lifecycle checks pass.",
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{identifier}-negative",
                            "status": "verified",
                            "kind": "integration-test",
                            "description": "The auth proof rejects contract drift or incorrect role behavior.",
                            "locator": "product/prove_auth_fixture.py",
                            "commandId": "auth-product-proof",
                            "expectedResult": "Invalid access behavior or contract state causes the proof to fail.",
                        }
                    ],
                    "releaseGateIds": ["auth-product-release"],
                }
            )
        return records

    def materialize_candidate(
        self, root: Path, *, allow_admin_without_role: bool = False
    ) -> tuple[object, Path, str, bytes, bytes]:
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
        self.assertTrue((target / ".template-composition/release/produce_release.py").is_file())

        self.add_admin_contracts(target)
        records = self.scaffold_product_evidence(target)
        self.write_json(
            target / "contracts/implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "commands": [
                    {
                        "id": "auth-product-proof",
                        "command": AUTH_PROOF_COMMAND,
                        "purpose": "Exercise realistic Webapp authentication, authorization, and route-state behavior.",
                    }
                ],
                "releaseGates": [
                    {
                        "id": "auth-product-release",
                        "purpose": "Block release unless the realistic Webapp auth proof passes.",
                        "commandIds": ["auth-product-proof"],
                    }
                ],
                "records": records,
            },
        )
        self.write_json(
            target / "contracts/release-execution.json",
            {
                "$schema": "../schemas/release-execution.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "commands": [
                    {
                        "commandId": "auth-product-proof",
                        "argv": ["python", "product/prove_auth_fixture.py"],
                        "workingDirectory": ".",
                    }
                ],
            },
        )

        product = target / "product"
        product.mkdir()
        (product / "auth_app.py").write_text(
            AUTH_APP_TEMPLATE.format(
                allow_admin_without_role=allow_admin_without_role
            ),
            encoding="utf-8",
        )
        (product / "prove_auth_fixture.py").write_text(
            AUTH_PROOF_SCRIPT,
            encoding="utf-8",
        )
        original_evidence = (target / "contracts/release-evidence.json").read_bytes()
        original_bundle = (target / "contracts/release-bundle.json").read_bytes()
        revision = helper.commit_candidate(target)
        return helper, target, revision, original_evidence, original_bundle

    def run_release(self, target: Path, revision: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-I",
                ".template-composition/release/produce_release.py",
                "--revision",
                revision,
            ],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_realistic_auth_fixture_reaches_transactional_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize_candidate(
                Path(temp_dir)
            )
            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "Webapp auth product proof: route access and UI-state behavior passed",
                result.stdout,
            )
            self.assertIn("Release evidence and bundle produced", result.stdout)

            evidence_path = target / "contracts/release-evidence.json"
            bundle_path = target / "contracts/release-bundle.json"
            self.assertNotEqual(evidence_path.read_bytes(), original_evidence)
            self.assertNotEqual(bundle_path.read_bytes(), original_bundle)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["subject"]["revision"], revision)
            self.assertEqual(evidence["decision"]["status"], "approved")
            self.assertEqual(bundle["subject"]["revision"], revision)
            self.assertEqual(bundle["handoff"]["status"], "ready")

            for validator in (
                ".template-composition/validators/validate_release_evidence.py",
                ".template-composition/validators/validate_release_bundle.py",
            ):
                validated = subprocess.run(
                    [
                        sys.executable,
                        validator,
                        ".",
                        "--expected-revision",
                        revision,
                    ],
                    cwd=target,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    validated.returncode,
                    0,
                    validated.stdout + validated.stderr,
                )

    def test_role_bypass_candidate_fails_release_and_restores_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize_candidate(
                Path(temp_dir),
                allow_admin_without_role=True,
            )
            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("canonical release evidence was restored", result.stderr)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )


if __name__ == "__main__":
    unittest.main()
