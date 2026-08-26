from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lifecycle_checkpoint_test_support import (
    create_planning_checkpoint,
    planning_evidence_from_product,
)

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
BROWSER_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "webapp_browser"
DOMAIN_IDS = {"surfaces", "routes", "ui_states", "viewports"}
PROOF_COMMAND = "python product/prove_webapp.py"
PROOF_SCRIPT = """from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from browser_probe import _open_webdriver_session, run_browser_contract_probe

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

viewports = json.loads(
    (ROOT / "contracts/viewports.json").read_text(encoding="utf-8")
)
client_url = (ROOT / "product/client.html").resolve().as_uri()
run_browser_contract_probe(client_url, viewports)
routes = json.loads((ROOT / "contracts/routes.json").read_text(encoding="utf-8"))["routes"]
assert len(routes) == 1
focus_target = routes[0]["accessibility"]["focusTarget"]
with _open_webdriver_session() as browser:
    browser.navigate(client_url)
    focus_result = browser.execute(
        '''
        const element = document.getElementById(arguments[0]);
        if (!element) return {exists: false};
        let visible = true;
        for (let current = element; current; current = current.parentElement) {
          const style = getComputedStyle(current);
          if (style.display === 'none' || style.visibility === 'hidden'
              || Number.parseFloat(style.opacity || '1') <= 0) visible = false;
        }
        const rect = element.getBoundingClientRect();
        return {
          exists: true,
          visible: visible && rect.width > 0 && rect.height > 0
            && rect.right > 0 && rect.bottom > 0
            && rect.left < window.innerWidth && rect.top < window.innerHeight,
          explicitlyFocusable: element.hasAttribute('tabindex'),
          focused: document.activeElement === element,
        };
        ''',
        focus_target,
    )
assert focus_result == {
    "exists": True,
    "visible": True,
    "explicitlyFocusable": True,
    "focused": True,
}, focus_result
print("Webapp product proof: contract lifecycle, route focus, and real-browser checks passed")
"""


class WebappProductizationAcceptanceTests(unittest.TestCase):
    def run_composer(
        self, *arguments: str
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"composer did not emit JSON: {exc}\n{result.stdout}\n{result.stderr}"
            )
        return result, payload

    def run_target(
        self, target: Path, relative: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, relative, *arguments],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def load_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_webapp_config(self, path: Path) -> None:
        self.write_json(
            path,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {
                    "include": ["lifecycle.release-bundle"],
                    "exclude": [],
                },
                "parameters": {},
            },
        )

    def git_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Webapp productization acceptance",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Webapp productization acceptance",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            }
        )
        return environment

    def run_git(self, target: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "maintenance.auto=false",
                "-c",
                "gc.auto=0",
                "-C",
                str(target),
                *arguments,
            ],
            env=self.git_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"git {' '.join(arguments)} failed\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def expected_targets(self, target: Path) -> list[dict]:
        manifest = self.load_json(target / "contracts/manifest.json")
        surfaces = self.load_json(target / "contracts/surfaces.json")
        routes = self.load_json(target / "contracts/routes.json")
        states = self.load_json(target / "contracts/ui-states.json")
        viewports = self.load_json(target / "contracts/viewports.json")

        expected: list[dict] = []
        expected.extend(
            {
                "kind": "contract-item",
                "contractId": "surfaces",
                "itemKind": "surface",
                "itemId": item["id"],
            }
            for item in surfaces["surfaces"]
        )
        expected.extend(
            {
                "kind": "contract-item",
                "contractId": "routes",
                "itemKind": "route",
                "itemId": item["id"],
            }
            for item in routes["routes"]
        )
        expected.extend(
            {
                "kind": "contract-item",
                "contractId": "ui_states",
                "itemKind": "ui-state",
                "itemId": item["id"],
            }
            for item in states["states"]
        )
        expected.extend(
            {
                "kind": "contract-item",
                "contractId": "viewports",
                "itemKind": "viewport",
                "itemId": item["id"],
            }
            for item in viewports["viewports"]
        )
        expected.extend(
            {
                "kind": "contract-item",
                "contractId": "viewports",
                "itemKind": "input-capability",
                "itemId": item,
            }
            for item in viewports["inputCapabilities"]
        )
        for entry in manifest["contracts"]:
            if entry["id"] not in DOMAIN_IDS:
                continue
            for transition in entry["versionHistory"][1:]:
                expected.append(
                    {
                        "kind": "contract-transition",
                        "contractId": entry["id"],
                        "fromVersion": transition["version"] - 1,
                        "toVersion": transition["version"],
                    }
                )
        return sorted(
            expected,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )

    def productize_implementation_evidence(self, target: Path) -> None:
        targets = self.expected_targets(target)
        self.assertTrue(targets)
        records = []
        requirements = []
        for index, evidence_target in enumerate(targets, 1):
            record_id = f"record-{index:03d}"
            browser_sensitive = (
                evidence_target.get("kind") == "contract-item"
                and (
                    (
                        evidence_target.get("contractId") == "viewports"
                        and evidence_target.get("itemKind")
                        in {"viewport", "input-capability"}
                    )
                    or (
                        evidence_target.get("contractId") == "routes"
                        and evidence_target.get("itemKind") == "route"
                    )
                )
            )
            proof_kind = "end-to-end-test" if browser_sensitive else "integration-test"
            implementation_locator = (
                "product/client.html"
                if browser_sensitive
                else "product/prove_webapp.py"
            )
            proof_locator = "product/prove_webapp.py"
            positive_description = (
                "The ChromeDriver proof executes route focus, responsive layout, or input behavior through the real browser interface."
                if browser_sensitive
                else "The product proof validates the positive contract path."
            )
            negative_description = (
                "The ChromeDriver proof rejects missing route focus, browser overflow, zoom locking, or failed input activation."
                if browser_sensitive
                else "The product proof keeps the declared target under validation."
            )
            records.append(
                {
                    "id": record_id,
                    "target": evidence_target,
                    "implementationBoundary": {
                        "status": "verified",
                        "description": "Acceptance fixture binds the target to its product proof.",
                        "locator": implementation_locator,
                    },
                    "positiveEvidence": [
                        {
                            "id": f"{record_id}-positive",
                            "status": "verified",
                            "kind": proof_kind,
                            "description": positive_description,
                            "locator": proof_locator,
                            "commandId": "webapp-proof",
                            "expectedResult": (
                                "The real-browser target checks pass."
                                if browser_sensitive
                                else "The contract lifecycle checks pass."
                            ),
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"{record_id}-negative",
                            "status": "verified",
                            "kind": proof_kind,
                            "description": negative_description,
                            "locator": proof_locator,
                            "commandId": "webapp-proof",
                            "expectedResult": (
                                "Invalid browser behavior causes the proof to fail."
                                if browser_sensitive
                                else "Invalid contract or evidence state causes the proof to fail."
                            ),
                        }
                    ],
                    "releaseGateIds": ["product-release"],
                }
            )
            requirements.append(
                {
                    "id": f"REQ-WEBAPP-{index:03d}",
                    "description": (
                        "Acceptance fixture requires implementation evidence for target "
                        + json.dumps(evidence_target, sort_keys=True, separators=(",", ":"))
                    ),
                    "targets": [evidence_target],
                    "recordIds": [record_id],
                    "requiredPositiveProofKinds": [proof_kind],
                }
            )

        product_evidence = {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 5,
            "mode": "product",
            "commands": [
                {
                    "id": "webapp-proof",
                    "command": PROOF_COMMAND,
                    "purpose": (
                        "Validate the generated Webapp contract lifecycle and "
                        "browser-sensitive targets before release."
                    ),
                }
            ],
            "releaseGates": [
                {
                    "id": "product-release",
                    "purpose": "Block release unless the Webapp product proof passes.",
                    "commandIds": ["webapp-proof"],
                }
            ],
            "records": records,
            "requirements": requirements,
        }
        product_evidence, planning_evidence = planning_evidence_from_product(
            product_evidence
        )
        self.write_json(
            target / "contracts/implementation-evidence.json",
            planning_evidence,
        )
        create_planning_checkpoint(target)

        self.write_json(
            target / "contracts/implementation-evidence.json",
            product_evidence,
        )
        self.write_json(
            target / "contracts/release-execution.json",
            {
                "$schema": "../schemas/release-execution.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "commands": [
                    {
                        "commandId": "webapp-proof",
                        "argv": ["python", "product/prove_webapp.py"],
                        "workingDirectory": ".",
                    }
                ],
            },
        )
        product = target / "product"
        product.mkdir()
        (product / "prove_webapp.py").write_text(PROOF_SCRIPT, encoding="utf-8")
        for name in ("browser_probe.py", "client.html"):
            (product / name).write_text(
                (BROWSER_FIXTURE_DIR / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def commit_candidate(self, target: Path) -> str:
        self.run_git(target, "init", "--quiet")
        self.run_git(target, "add", "--all", "--force")
        self.run_git(target, "commit", "--quiet", "--message", "Create Webapp product candidate")
        revision = self.run_git(
            target, "rev-parse", "--verify", "HEAD^{commit}"
        ).stdout.strip()
        self.assertRegex(revision, r"^[0-9a-f]{40}$")
        return revision

    def timestamp(self, value: datetime) -> str:
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    def write_release_evidence(
        self,
        target: Path,
        revision: str,
        *,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        decided_at = datetime.now(timezone.utc)
        generated_at = datetime.now(timezone.utc)
        self.write_json(
            target / "contracts/release-evidence.json",
            {
                "$schema": "../schemas/release-evidence.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "subject": {
                    "revision": revision,
                    "description": "Exact product candidate proven by the acceptance fixture.",
                },
                "provenance": {
                    "kind": "local-run",
                    "id": "webapp-productization-acceptance",
                    "locator": "tests/test_webapp_productization_acceptance.py",
                    "generatedAt": self.timestamp(generated_at),
                },
                "decision": {
                    "status": "approved",
                    "decidedAt": self.timestamp(decided_at),
                    "description": "The candidate proof and selected release gate passed.",
                },
                "commandResults": [
                    {
                        "commandId": "webapp-proof",
                        "commandDigest": hashlib.sha256(
                            PROOF_COMMAND.encode("utf-8")
                        ).hexdigest(),
                        "status": "passed",
                        "exitCode": 0,
                        "startedAt": self.timestamp(started_at),
                        "completedAt": self.timestamp(completed_at),
                        "resultLocator": (
                            "tests/test_webapp_productization_acceptance.py#webapp-proof"
                        ),
                    }
                ],
                "gateResults": [
                    {
                        "gateId": "product-release",
                        "status": "passed",
                        "resultLocator": (
                            "tests/test_webapp_productization_acceptance.py#product-release"
                        ),
                    }
                ],
            },
        )

    def write_release_bundle(self, target: Path, revision: str) -> None:
        manifest = self.load_json(target / "contracts/manifest.json")
        artifacts = []
        for entry in manifest["contracts"]:
            if entry["id"] == "release_bundle":
                continue
            document = target / entry["document"]
            artifacts.append(
                {
                    "contractId": entry["id"],
                    "path": entry["document"],
                    "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
                }
            )
        self.write_json(
            target / "contracts/release-bundle.json",
            {
                "$schema": "../schemas/release-bundle.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "subject": {
                    "revision": revision,
                    "description": "Exact product candidate ready for release handoff.",
                },
                "provenance": {
                    "kind": "local-run",
                    "id": "webapp-productization-acceptance-bundle",
                    "locator": "tests/test_webapp_productization_acceptance.py",
                    "generatedAt": self.timestamp(datetime.now(timezone.utc)),
                },
                "handoff": {
                    "status": "ready",
                    "description": "All registered contract artifacts are digest-closed.",
                },
                "artifacts": artifacts,
            },
        )

    def create_product_candidate(
        self, root: Path
    ) -> tuple[Path, str]:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_webapp_config(config)

        result, payload = self.run_composer(
            "apply",
            "--config",
            str(config),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)
        self.productize_implementation_evidence(target)
        revision = self.commit_candidate(target)

        started_at = datetime.now(timezone.utc)
        proof = self.run_target(target, "product/prove_webapp.py")
        completed_at = datetime.now(timezone.utc)
        self.assertEqual(
            proof.returncode,
            0,
            f"stdout:\n{proof.stdout}\nstderr:\n{proof.stderr}",
        )
        self.assertIn(
            "Browser Webapp proof: responsive layout, scrolling, zoom, orientation, and declared input capabilities passed",
            proof.stdout,
        )
        self.assertIn(
            "Webapp product proof: contract lifecycle, route focus, and real-browser checks passed",
            proof.stdout,
        )

        self.write_release_evidence(
            target,
            revision,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.write_release_bundle(target, revision)
        return target, revision

    def assert_validator_passes(
        self, target: Path, relative: str, *arguments: str
    ) -> None:
        result = self.run_target(target, relative, *arguments)
        self.assertEqual(
            result.returncode,
            0,
            f"{relative}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_composer_generated_webapp_reaches_revision_bound_product_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision = self.create_product_candidate(Path(temp_dir))

            for relative, arguments in (
                ("scripts/validate_contracts.py", ()),
                (
                    ".template-composition/validators/validate_contract_evolution.py",
                    (".",),
                ),
                (
                    ".template-composition/validators/validate_implementation_evidence.py",
                    (".",),
                ),
                (
                    ".template-composition/validators/validate_lifecycle_checkpoints.py",
                    (".",),
                ),
                (
                    ".template-composition/validators/validate_release_execution.py",
                    (".",),
                ),
                ("scripts/validate_webapp_evidence.py", ()),
                (
                    ".template-composition/validators/validate_release_evidence.py",
                    (".", "--expected-revision", revision),
                ),
                (
                    ".template-composition/validators/validate_release_bundle.py",
                    (".", "--expected-revision", revision),
                ),
            ):
                with self.subTest(validator=relative):
                    self.assert_validator_passes(target, relative, *arguments)

            result, payload = self.run_composer(
                "validate", "--target", str(target)
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")

    def test_revision_digest_and_chronology_binding_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision = self.create_product_candidate(Path(temp_dir))
            release_path = target / "contracts/release-evidence.json"
            original = self.load_json(release_path)

            mismatch = self.run_target(
                target,
                ".template-composition/validators/validate_release_evidence.py",
                ".",
                "--expected-revision",
                "f" * 40,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn(
                "release subject does not match expected revision",
                mismatch.stderr,
            )

            drifted = json.loads(json.dumps(original))
            drifted["commandResults"][0]["commandDigest"] = "0" * 64
            self.write_json(release_path, drifted)
            digest = self.run_target(
                target,
                ".template-composition/validators/validate_release_evidence.py",
                ".",
                "--expected-revision",
                revision,
            )
            self.assertNotEqual(digest.returncode, 0)
            self.assertIn(
                "commandDigest does not match authoritative command",
                digest.stderr,
            )

            invalid_chronology = json.loads(json.dumps(original))
            invalid_chronology["commandResults"][0][
                "completedAt"
            ] = "2000-01-01T00:00:00Z"
            self.write_json(release_path, invalid_chronology)
            chronology = self.run_target(
                target,
                ".template-composition/validators/validate_release_evidence.py",
                ".",
                "--expected-revision",
                revision,
            )
            self.assertNotEqual(chronology.returncode, 0)
            self.assertIn("completedAt precedes startedAt", chronology.stderr)

            self.write_json(release_path, original)
            self.assert_validator_passes(
                target,
                ".template-composition/validators/validate_release_bundle.py",
                ".",
                "--expected-revision",
                revision,
            )

    def test_managed_workflow_defers_product_release_binding(self) -> None:
        workflow = (
            ROOT
            / "components/artifact.webapp-core/files/.github/workflows/validate-webapp.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("python .template-composition/validate.py .", workflow)
        self.assertNotIn("validate_release_execution.py", workflow)
        self.assertNotIn("release-modes", workflow)
        self.assertNotIn("--expected-revision", workflow)
        self.assertNotIn("shell: bash", workflow)


if __name__ == "__main__":
    unittest.main()
