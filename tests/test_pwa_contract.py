from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components" / "capability.pwa"
FILES = COMPONENT / "files"
VALIDATOR = FILES / ".template-composition" / "validators" / "validate_pwa.py"


class PwaContractTests(unittest.TestCase):
    def load(self, relative: str) -> dict:
        return json.loads((FILES / relative).read_text(encoding="utf-8"))

    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def webapp_contracts(self) -> tuple[dict, dict, dict]:
        routes = {
            "routes": [
                {
                    "id": "home",
                    "path": "/",
                    "surface": "primary",
                    "canonical": True,
                    "deepLink": True,
                }
            ]
        }
        surfaces = {
            "surfaces": [
                {
                    "id": "primary",
                    "dataClassifications": ["public", "internal"],
                }
            ]
        }
        states = {
            "states": [
                {"id": "offline", "category": "connectivity"},
                {"id": "sync-pending", "category": "progress"},
                {"id": "sync-failed", "category": "error"},
                {"id": "update-available", "category": "content"},
                {"id": "update-applying", "category": "progress"},
                {"id": "update-failed", "category": "error"},
            ]
        }
        return routes, surfaces, states

    def product_contracts(self) -> tuple[dict, dict, dict]:
        manifest = {
            "$schema": "../schemas/pwa-manifest.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "manifestPath": "/manifest.webmanifest",
            "name": "Example PWA",
            "shortName": "Example",
            "startRouteId": "home",
            "scope": "/",
            "display": "standalone",
            "orientation": "any",
            "icons": [
                {
                    "id": "primary",
                    "href": "/icons/app.svg",
                    "mediaType": "image/svg+xml",
                    "sizes": ["any"],
                    "purposes": ["any", "maskable"],
                }
            ],
        }
        offline = {
            "$schema": "../schemas/pwa-offline.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "availability": "offline-capable",
            "serviceWorkerScope": "/",
            "controlledRouteIds": ["home"],
            "offlineStateId": "offline",
            "navigationFallbackRouteId": "home",
            "surfacePolicies": [
                {
                    "surfaceId": "primary",
                    "cacheableDataClassifications": ["public"],
                    "readBehavior": "network-first",
                }
            ],
            "mutationBehavior": "queue-until-online",
            "pendingStateId": "sync-pending",
            "failureStateId": "sync-failed",
        }
        update = {
            "$schema": "../schemas/pwa-update.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "activation": "user-confirmed",
            "unsavedChangesPolicy": "preserve",
            "updateAvailableStateId": "update-available",
            "applyingStateId": "update-applying",
            "failureStateId": "update-failed",
        }
        return manifest, offline, update

    def run_validator(
        self,
        manifest: dict,
        offline: dict,
        update: dict,
        *,
        evidence_mode: str = "product",
        routes: dict | None = None,
        surfaces: dict | None = None,
        states: dict | None = None,
    ) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        default_routes, default_surfaces, default_states = self.webapp_contracts()
        documents = {
            "contracts/pwa-manifest.json": manifest,
            "contracts/pwa-offline.json": offline,
            "contracts/pwa-update.json": update,
            "contracts/routes.json": routes or default_routes,
            "contracts/surfaces.json": surfaces or default_surfaces,
            "contracts/ui-states.json": states or default_states,
            "contracts/implementation-evidence.json": {"mode": evidence_mode},
        }
        for relative, value in documents.items():
            self.write_json(root / relative, value)
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_descriptor_registers_three_pwa_contracts_without_runtime_dependency(self) -> None:
        descriptor = json.loads((COMPONENT / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["version"], 1)
        self.assertEqual(descriptor["requires"], ["lifecycle.implementation-evidence"])
        self.assertEqual(
            [registration["id"] for registration in descriptor["contract_registrations"]],
            ["pwa_manifest", "pwa_offline", "pwa_update"],
        )
        self.assertNotIn("capability.runtime", descriptor["requires"])
        self.assertFalse(any(item.startswith("artifact.") for item in descriptor["requires"]))

    def test_template_and_product_contracts_are_schema_valid(self) -> None:
        for name in ("pwa-manifest", "pwa-offline", "pwa-update"):
            schema = self.load(f"schemas/{name}.schema.json")
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(self.load(f"contracts/{name}.json"))

        manifest, offline, update = self.product_contracts()
        for name, document in (
            ("pwa-manifest", manifest),
            ("pwa-offline", offline),
            ("pwa-update", update),
        ):
            Draft202012Validator(self.load(f"schemas/{name}.schema.json")).validate(document)

    def test_network_only_product_does_not_require_service_worker_fields(self) -> None:
        manifest, _offline, update = self.product_contracts()
        offline = {
            "$schema": "../schemas/pwa-offline.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "availability": "network-only",
        }
        Draft202012Validator(self.load("schemas/pwa-offline.schema.json")).validate(offline)
        result = self.run_validator(manifest, offline, update)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_product_cross_contract_semantics_validate(self) -> None:
        manifest, offline, update = self.product_contracts()
        result = self.run_validator(manifest, offline, update)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PWA product semantics", result.stdout)

    def test_start_route_must_be_canonical_deep_linkable_and_inside_scope(self) -> None:
        manifest, offline, update = self.product_contracts()
        manifest["scope"] = "/app/"
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside manifest scope", result.stderr)

        routes, surfaces, states = self.webapp_contracts()
        routes["routes"][0]["canonical"] = False
        routes["routes"][0]["deepLink"] = False
        result = self.run_validator(
            *self.product_contracts(),
            routes=routes,
            surfaces=surfaces,
            states=states,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be canonical", result.stderr)
        self.assertIn("must be deep-linkable", result.stderr)

    def test_offline_cache_policy_must_follow_surface_data_classification_authority(self) -> None:
        manifest, offline, update = self.product_contracts()
        offline["surfacePolicies"][0]["cacheableDataClassifications"] = ["secret"]
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("undeclared data classifications", result.stderr)

    def test_offline_and_update_states_have_semantic_category_floors(self) -> None:
        manifest, offline, update = self.product_contracts()
        _routes, surfaces, states = self.webapp_contracts()
        states["states"][0]["category"] = "content"
        states["states"][4]["category"] = "content"
        result = self.run_validator(
            manifest,
            offline,
            update,
            surfaces=surfaces,
            states=states,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("offlineStateId", result.stderr)
        self.assertIn("applyingStateId", result.stderr)

    def test_immediate_update_cannot_claim_blocked_activation(self) -> None:
        manifest, offline, update = self.product_contracts()
        update["activation"] = "immediate"
        update["unsavedChangesPolicy"] = "block-activation"
        update.pop("updateAvailableStateId")
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("immediate PWA update activation", result.stderr)

    def test_pwa_and_implementation_evidence_modes_move_together(self) -> None:
        manifest, offline, update = self.product_contracts()
        result = self.run_validator(manifest, offline, update, evidence_mode="planning")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires implementation-evidence mode", result.stderr)


if __name__ == "__main__":
    unittest.main()
