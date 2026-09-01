from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


def config(*, include: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "recipe": "website",
        "components": {"include": include or [], "exclude": []},
        "parameters": {},
    }


class WebsiteComposerAcceptanceTests(unittest.TestCase):
    def write_config(self, root: Path, value: dict) -> Path:
        path = root / "composition.json"
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def run_composer(
        self,
        command: str,
        *,
        target: Path,
        config_path: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        args = [sys.executable, str(COMPOSER), command, "--target", str(target)]
        if config_path is not None:
            args.extend(["--config", str(config_path)])
        result = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"composer did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def test_minimal_website_plan_has_shared_web_and_evidence_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config())
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload["resolved_components"],
                [
                    "artifact.website-core",
                    "foundation.web",
                    "lifecycle.composition-state",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                    "lifecycle.lifecycle-checkpoints",
                ],
            )
            self.assertNotIn("artifact.webapp-core", payload["resolved_components"])
            self.assertNotIn("capability.pwa", payload["resolved_components"])
            self.assertNotIn("capability.runtime", payload["resolved_components"])

    def test_website_pwa_is_explicit_and_does_not_pull_webapp_private_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root, config(include=["capability.pwa"])
            )
            target = root / "consumer"
            result, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "applied")
            lock = json.loads(
                (target / ".template-composition" / "lock.json").read_text(
                    encoding="utf-8"
                )
            )
            resolved = [entry["id"] for entry in lock["resolved_components"]]
            self.assertIn("artifact.website-core", resolved)
            self.assertIn("foundation.web", resolved)
            self.assertIn("capability.pwa", resolved)
            self.assertNotIn("artifact.webapp-core", resolved)
            for required in (
                "site-structure.json",
                "document-metadata.json",
                "site-discovery.json",
                "routes.json",
                "pwa-manifest.json",
                "pwa-offline.json",
                "pwa-update.json",
            ):
                self.assertTrue((target / "contracts" / required).is_file(), required)
            for forbidden in (
                "application-routes.json",
                "surfaces.json",
                "ui-states.json",
            ):
                self.assertFalse((target / "contracts" / forbidden).exists(), forbidden)

    def test_website_service_materializes_runtime_and_validates_without_webapp_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root, config(include=["capability.service"])
            )
            target = root / "consumer"
            applied, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(payload["status"], "applied")

            lock = json.loads(
                (target / ".template-composition" / "lock.json").read_text(
                    encoding="utf-8"
                )
            )
            resolved = [entry["id"] for entry in lock["resolved_components"]]
            for required_component in (
                "artifact.website-core",
                "foundation.web",
                "capability.service",
                "capability.runtime",
            ):
                self.assertIn(required_component, resolved)
            self.assertNotIn("artifact.webapp-core", resolved)

            for required_contract in (
                "routes.json",
                "site-structure.json",
                "document-metadata.json",
                "site-discovery.json",
                "service-interface.json",
            ):
                self.assertTrue(
                    (target / "contracts" / required_contract).is_file(),
                    required_contract,
                )
            for forbidden_contract in (
                "application-routes.json",
                "surfaces.json",
                "ui-states.json",
            ):
                self.assertFalse(
                    (target / "contracts" / forbidden_contract).exists(),
                    forbidden_contract,
                )

            for required_material in (
                "SERVICE_INTERFACE.md",
                "RUNTIME.md",
                "docs/runtime-selection.md",
                "schemas/service-interface.schema.json",
                ".template-composition/validators/validate_service_interface.py",
                "docs/migrations/service-interface-v1-to-v2.md",
            ):
                self.assertTrue((target / required_material).is_file(), required_material)

            validated, validation = self.run_composer("validate", target=target)
            self.assertEqual(
                validated.returncode,
                0,
                validated.stdout + validated.stderr,
            )
            self.assertEqual(validation["status"], "valid")

    def test_runtime_backed_website_is_an_orthogonal_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root, config(include=["capability.runtime"])
            )
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("artifact.website-core", payload["resolved_components"])
            self.assertIn("foundation.web", payload["resolved_components"])
            self.assertIn("capability.runtime", payload["resolved_components"])
            self.assertNotIn("artifact.webapp-core", payload["resolved_components"])
            self.assertNotIn("capability.pwa", payload["resolved_components"])

    def test_multi_page_website_contracts_validate_without_application_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config())
            target = root / "consumer"
            applied, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(payload["status"], "applied")

            routes_path = target / "contracts" / "routes.json"
            routes = json.loads(routes_path.read_text(encoding="utf-8"))
            routes["routes"].append(
                {
                    "id": "about",
                    "path": "/about",
                    "canonical": True,
                    "aliases": [],
                    "deepLink": True,
                    "accessibility": {
                        "documentTitleRequired": True,
                        "focusTarget": "main-heading",
                    },
                }
            )
            routes_path.write_text(json.dumps(routes, indent=2) + "\n", encoding="utf-8")

            structure_path = target / "contracts" / "site-structure.json"
            structure = json.loads(structure_path.read_text(encoding="utf-8"))
            structure["pages"].append(
                {
                    "id": "about",
                    "routeId": "about",
                    "role": "content",
                    "title": "About",
                    "parentPageId": "home",
                }
            )
            structure_path.write_text(
                json.dumps(structure, indent=2) + "\n", encoding="utf-8"
            )

            metadata_path = target / "contracts" / "document-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["pages"].append(
                {
                    "pageId": "about",
                    "title": "About",
                    "description": "About this Website.",
                    "indexability": "index",
                    "canonicalPathPolicy": "route-canonical",
                    "socialPreview": "none",
                }
            )
            metadata_path.write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )

            discovery_path = target / "contracts" / "site-discovery.json"
            discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
            discovery["sitemap"]["pageIds"].append("about")
            discovery_path.write_text(
                json.dumps(discovery, indent=2) + "\n", encoding="utf-8"
            )

            validator = target / "scripts" / "validate_website_contracts.py"
            validation = subprocess.run(
                [sys.executable, str(validator), str(target)],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                validation.returncode,
                0,
                validation.stdout + validation.stderr,
            )
            for forbidden in (
                "application-routes.json",
                "surfaces.json",
                "ui-states.json",
            ):
                self.assertFalse((target / "contracts" / forbidden).exists(), forbidden)


if __name__ == "__main__":
    unittest.main()
