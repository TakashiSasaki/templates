from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_webapp_productization_acceptance as product_helpers


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "webapp_auth"
AUTH_PROOF_COMMAND = "python product/prove_auth_fixture.py"


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
                "diagnostic": False,
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

    def target_locator(self, evidence_target: dict) -> str:
        if evidence_target.get("contractId") == "viewports":
            return "product/client.html"
        if evidence_target.get("kind") == "contract-transition":
            return "product/prove_auth_fixture.py"
        return "product/auth_app.py"

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
        self.assertEqual(
            worklist["format"], "webapp-implementation-evidence-worklist"
        )
        self.assertEqual(worklist["recordCount"], len(worklist["records"]))

        targets = [record["target"] for record in worklist["records"]]
        for expected in (
            {
                "kind": "contract-item",
                "contractId": "surfaces",
                "itemKind": "surface",
                "itemId": "admin",
            },
            {
                "kind": "contract-item",
                "contractId": "routes",
                "itemKind": "route",
                "itemId": "admin",
            },
        ):
            self.assertIn(expected, targets)

        records: list[dict] = []
        for skeleton in worklist["records"]:
            identifier = skeleton["id"]
            implementation_locator = self.target_locator(skeleton["target"])
            records.append(
                {
                    "id": identifier,
                    "target": skeleton["target"],
                    "implementationBoundary": {
                        "status": "verified",
                        "description": (
                            "The executable browser auth fixture implements this "
                            "generated Webapp target."
                        ),
                        "locator": implementation_locator,
                    },
                    "positiveEvidence": [
                        {
                            "id": f"{identifier}-positive",
                            "status": "verified",
                            "kind": "integration-test",
                            "description": (
                                "The auth proof exercises the target through contract, "
                                "browser-surface, and HTTP behavior checks."
                            ),
                            "locator": "product/prove_auth_fixture.py",
                            "commandId": "auth-product-proof",
                            "expectedResult": (
                                "The declared route, state, access, viewport, input, "
                                "and lifecycle checks pass."
                            ),
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{identifier}-negative",
                            "status": "verified",
                            "kind": "integration-test",
                            "description": (
                                "The auth proof rejects contract drift or incorrect "
                                "role/browser behavior."
                            ),
                            "locator": "product/prove_auth_fixture.py",
                            "commandId": "auth-product-proof",
                            "expectedResult": (
                                "Invalid access, browser, or contract behavior causes "
                                "the proof to fail."
                            ),
                        }
                    ],
                    "releaseGateIds": ["auth-product-release"],
                }
            )
        return records

    def write_product_files(
        self, target: Path, *, allow_admin_without_role: bool
    ) -> None:
        auth_source = (FIXTURE_DIR / "auth_app.py").read_text(encoding="utf-8")
        replacement = "True" if allow_admin_without_role else "False"
        auth_source = auth_source.replace(
            "__ALLOW_ADMIN_WITHOUT_ROLE__", replacement
        )
        self.assertNotIn("__ALLOW_ADMIN_WITHOUT_ROLE__", auth_source)

        product = target / "product"
        product.mkdir()
        (product / "auth_app.py").write_text(auth_source, encoding="utf-8")
        for name in ("prove_auth_fixture.py", "client.html"):
            (product / name).write_text(
                (FIXTURE_DIR / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

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
        self.assertTrue(
            (target / ".template-composition/release/produce_release.py").is_file()
        )

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
                        "purpose": (
                            "Exercise realistic browser Webapp authentication, "
                            "authorization, route-state, viewport, and input behavior."
                        ),
                    }
                ],
                "releaseGates": [
                    {
                        "id": "auth-product-release",
                        "purpose": (
                            "Block release unless the realistic browser Webapp proof "
                            "passes."
                        ),
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
        self.write_product_files(
            target,
            allow_admin_without_role=allow_admin_without_role,
        )

        original_evidence = (target / "contracts/release-evidence.json").read_bytes()
        original_bundle = (target / "contracts/release-bundle.json").read_bytes()
        revision = helper.commit_candidate(target)
        return helper, target, revision, original_evidence, original_bundle

    def run_release(
        self, target: Path, revision: str
    ) -> subprocess.CompletedProcess[str]:
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
            _, target, revision, original_evidence, original_bundle = (
                self.materialize_candidate(Path(temp_dir))
            )
            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "Webapp auth product proof: route access, UI-state, and viewport behavior passed",
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
            _, target, revision, original_evidence, original_bundle = (
                self.materialize_candidate(
                    Path(temp_dir),
                    allow_admin_without_role=True,
                )
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
