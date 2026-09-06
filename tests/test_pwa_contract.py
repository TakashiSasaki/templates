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

    def shared_route(self, route_id: str, path: str) -> dict:
        return {
            "id": route_id,
            "path": path,
            "canonical": True,
            "aliases": [],
            "deepLink": True,
            "accessibility": {
                "documentTitleRequired": True,
                "focusTarget": "main-heading",
            },
        }

    def web_routes(self) -> dict:
        return {
            "$schema": "../schemas/routes.schema.json",
            "schemaVersion": 5,
            "routes": [self.shared_route("home", "/")],
        }

    def product_contracts(self) -> tuple[dict, dict, dict]:
        manifest = {
            "$schema": "../schemas/pwa-manifest.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "manifestPath": "/manifest.webmanifest",
            "manifestLinkRequired": True,
            "secureContextRequired": True,
            "name": "Example PWA",
            "shortName": "Example",
            "startRouteId": "home",
            "scope": "/",
            "display": "standalone",
            "orientation": "any",
            "icons": [
                {"id": "vector", "href": "/icons/app.svg", "mediaType": "image/svg+xml", "sizes": ["any"], "purposes": ["any"]},
                {"id": "raster-192", "href": "/icons/app-192.png", "mediaType": "image/png", "sizes": ["192x192"], "purposes": ["any"]},
                {"id": "raster-512", "href": "/icons/app-512.png", "mediaType": "image/png", "sizes": ["512x512"], "purposes": ["any"]},
                {"id": "maskable-512", "href": "/icons/app-maskable-512.png", "mediaType": "image/png", "sizes": ["512x512"], "purposes": ["maskable"]},
            ],
            "vectorIconPolicy": "prefer-svg-when-compatible",
            "vectorIconException": None,
            "platformCompatibility": {
                "android": {"requiredRasterSizes": ["192x192", "512x512"], "maskableIconRequired": True},
                "ios": {"homeScreenIcon": {"relation": "apple-touch-icon", "href": "/icons/apple-touch-icon.png", "mediaType": "image/png", "sizes": ["180x180"]}},
            },
        }
        offline = {
            "$schema": "../schemas/pwa-offline.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "availability": "offline-capable",
            "serviceWorkerScope": "/",
            "controlledRouteIds": ["home"],
            "navigationFallbackRouteId": "home",
            "routePolicies": [{"routeId": "home", "offlineReadBehavior": "cached-content-when-available"}],
            "networkUnavailablePresentation": "required-visible",
            "freshnessUnknownPresentation": "required-visible",
            "revalidatingPresentation": "required-visible",
            "cacheStrategy": "implementation-defined",
            "onlineFreshnessPolicy": "revalidate-before-display",
            "offlineFreshnessPolicy": "indicate-unverified",
            "mutationBehavior": "queue-until-online",
            "pendingMutationPresentation": "required-visible",
            "failedMutationPresentation": "required-visible",
        }
        update = {
            "$schema": "../schemas/pwa-update.schema.json",
            "schemaVersion": 2,
            "mode": "product",
            "updateDetection": "observable",
            "activation": "user-confirmed",
            "unsavedChangesPolicy": "preserve",
            "updateAvailablePresentation": "required-visible",
            "applyingUpdatePresentation": "required-visible",
            "failedUpdatePresentation": "required-visible",
        }
        return manifest, offline, update

    def run_validator(self, manifest: dict, offline: dict, update: dict, *, evidence_mode: str = "product", routes: dict | None = None) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        documents = {
            "contracts/pwa-manifest.json": manifest,
            "contracts/pwa-offline.json": offline,
            "contracts/pwa-update.json": update,
            "contracts/routes.json": self.web_routes() if routes is None else routes,
            "contracts/implementation-evidence.json": {"mode": evidence_mode},
        }
        for relative, value in documents.items():
            self.write_json(root / relative, value)
        return subprocess.run([sys.executable, str(VALIDATOR), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_descriptor_keeps_pwa_artifact_neutral_and_versions_breaking_contracts(self) -> None:
        descriptor = json.loads((COMPONENT / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["version"], 4)
        self.assertEqual(descriptor["requires"], ["lifecycle.implementation-evidence"])
        registrations = {item["id"]: item for item in descriptor["contract_registrations"]}
        self.assertEqual(registrations["pwa_manifest"]["document_schema_version"], 1)
        self.assertEqual(registrations["pwa_offline"]["document_schema_version"], 2)
        self.assertEqual(registrations["pwa_update"]["document_schema_version"], 2)
        self.assertEqual([item["version"] for item in registrations["pwa_offline"]["version_history"]], [1, 2])
        self.assertEqual([item["version"] for item in registrations["pwa_update"]["version_history"]], [1, 2])
        self.assertFalse(any(item.startswith("artifact.") or item.startswith("foundation.") for item in descriptor["requires"]))

    def test_template_and_product_contracts_are_schema_valid(self) -> None:
        for name in ("pwa-manifest", "pwa-offline", "pwa-update"):
            schema = self.load(f"schemas/{name}.schema.json")
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(self.load(f"contracts/{name}.json"))
        for name, document in zip(("pwa-manifest", "pwa-offline", "pwa-update"), self.product_contracts()):
            errors = list(Draft202012Validator(self.load(f"schemas/{name}.schema.json")).iter_errors(document))
            self.assertEqual(errors, [], [error.message for error in errors])

    def test_product_pwa_validates_without_webapp_private_contracts(self) -> None:
        result = self.run_validator(*self.product_contracts())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("route-scoped offline freshness", result.stdout)
        source = VALIDATOR.read_text(encoding="utf-8")
        for forbidden in ("application-routes.json", "surfaces.json", "ui-states.json"):
            self.assertNotIn(forbidden, source)
        for schema_name in ("pwa-offline", "pwa-update"):
            schema_text = (FILES / f"schemas/{schema_name}.schema.json").read_text(encoding="utf-8")
            for forbidden in ("surfaceId", "StateId", "ui-states"):
                self.assertNotIn(forbidden, schema_text)

    def test_template_mode_does_not_require_shared_routes(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name in ("pwa-manifest", "pwa-offline", "pwa-update"):
            self.write_json(root / "contracts" / f"{name}.json", self.load(f"contracts/{name}.json"))
        self.write_json(root / "contracts/implementation-evidence.json", {"mode": "template"})
        result = subprocess.run([sys.executable, str(VALIDATOR), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_planning_mode_uses_same_artifact_neutral_semantics(self) -> None:
        manifest, offline, update = self.product_contracts()
        for document in (manifest, offline, update):
            document["mode"] = "planning"
        result = self.run_validator(manifest, offline, update, evidence_mode="planning")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_route_policies_are_exactly_the_controlled_route_set(self) -> None:
        manifest, offline, update = self.product_contracts()
        offline["routePolicies"] = []
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing explicit offline route policies", result.stderr)

        manifest, offline, update = self.product_contracts()
        offline["routePolicies"].append({"routeId": "other", "offlineReadBehavior": "network-unavailable-presentation"})
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references unknown route", result.stderr)
        self.assertIn("do not belong to controlled routes", result.stderr)

        manifest, offline, update = self.product_contracts()
        offline["routePolicies"].append(copy.deepcopy(offline["routePolicies"][0]))
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate PWA offline route policy", result.stderr)

    def test_start_route_must_be_canonical_deep_linkable_and_inside_scope(self) -> None:
        manifest, offline, update = self.product_contracts()
        manifest["scope"] = "/app/"
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside manifest scope", result.stderr)

        routes = self.web_routes()
        routes["routes"][0]["canonical"] = False
        routes["routes"][0]["deepLink"] = False
        result = self.run_validator(*self.product_contracts(), routes=routes)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be canonical", result.stderr)
        self.assertIn("must be deep-linkable", result.stderr)

    def test_sub_scoped_pwa_accepts_scope_root_and_nested_routes(self) -> None:
        manifest, offline, update = self.product_contracts()
        manifest["scope"] = "/app/"
        offline["serviceWorkerScope"] = "/app/"
        routes = self.web_routes()
        routes["routes"] = [self.shared_route("home", "/app"), self.shared_route("docs", "/app/docs")]
        offline["controlledRouteIds"] = ["home", "docs"]
        offline["routePolicies"].append({"routeId": "docs", "offlineReadBehavior": "cached-content-when-available"})
        result = self.run_validator(manifest, offline, update, routes=routes)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_navigation_fallback_must_exist_and_be_controlled(self) -> None:
        manifest, offline, update = self.product_contracts()
        offline["navigationFallbackRouteId"] = "unknown"
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references unknown route", result.stderr)

        manifest, offline, update = self.product_contracts()
        routes = self.web_routes()
        routes["routes"].append(self.shared_route("other", "/other"))
        offline["navigationFallbackRouteId"] = "other"
        result = self.run_validator(manifest, offline, update, routes=routes)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be included in controlledRouteIds", result.stderr)

    def test_cache_algorithm_and_required_presentations_fail_closed(self) -> None:
        _manifest, offline, _update = self.product_contracts()
        validator = Draft202012Validator(self.load("schemas/pwa-offline.schema.json"))
        concrete = copy.deepcopy(offline)
        concrete["cacheStrategy"] = "network-first"
        self.assertTrue(list(validator.iter_errors(concrete)))
        for required in ("networkUnavailablePresentation", "freshnessUnknownPresentation", "revalidatingPresentation"):
            incomplete = copy.deepcopy(offline)
            incomplete.pop(required)
            self.assertTrue(list(validator.iter_errors(incomplete)), required)

    def test_queued_mutations_require_pwa_owned_presentations(self) -> None:
        validator = Draft202012Validator(self.load("schemas/pwa-offline.schema.json"))
        _manifest, offline, _update = self.product_contracts()
        for field in ("pendingMutationPresentation", "failedMutationPresentation"):
            incomplete = copy.deepcopy(offline)
            incomplete.pop(field)
            self.assertTrue(list(validator.iter_errors(incomplete)), field)
        rejected = copy.deepcopy(offline)
        rejected["mutationBehavior"] = "reject-when-offline"
        rejected.pop("pendingMutationPresentation")
        rejected.pop("failedMutationPresentation")
        self.assertEqual(list(validator.iter_errors(rejected)), [])

    def test_update_contract_uses_observable_presentations_not_ui_state_ids(self) -> None:
        validator = Draft202012Validator(self.load("schemas/pwa-update.schema.json"))
        _manifest, _offline, update = self.product_contracts()
        next_launch = copy.deepcopy(update)
        next_launch["activation"] = "next-launch"
        self.assertTrue(list(validator.iter_errors(next_launch)))
        next_launch.pop("updateAvailablePresentation")
        self.assertEqual(list(validator.iter_errors(next_launch)), [])
        immediate = copy.deepcopy(next_launch)
        immediate["activation"] = "immediate"
        immediate["unsavedChangesPolicy"] = "block-activation"
        self.assertTrue(list(validator.iter_errors(immediate)))

    def test_duplicate_manifest_icons_and_platform_compatibility_fail_closed(self) -> None:
        manifest, offline, update = self.product_contracts()
        duplicate = copy.deepcopy(manifest["icons"][0])
        duplicate["href"] = "/icons/other.svg"
        manifest["icons"].append(duplicate)
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate PWA manifest icon id", result.stderr)

        manifest, offline, update = self.product_contracts()
        manifest["icons"] = [icon for icon in manifest["icons"] if "192x192" not in icon["sizes"]]
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Android compatibility raster size", result.stderr)

    def test_pwa_and_implementation_evidence_modes_move_together(self) -> None:
        manifest, offline, update = self.product_contracts()
        result = self.run_validator(manifest, offline, update, evidence_mode="planning")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires implementation-evidence mode", result.stderr)


if __name__ == "__main__":
    unittest.main()
