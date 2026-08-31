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
                {"id": "network-unavailable", "scope": "global", "category": "connectivity"},
                {"id": "freshness-unverified", "scope": "global", "category": "degraded"},
                {"id": "revalidating", "scope": "global", "category": "progress"},
                {"id": "sync-pending", "scope": "global", "category": "progress"},
                {"id": "sync-failed", "scope": "global", "category": "error"},
                {"id": "update-available", "scope": "global", "category": "content"},
                {"id": "update-applying", "scope": "global", "category": "progress"},
                {"id": "update-failed", "scope": "global", "category": "error"},
            ]
        }
        return routes, surfaces, states

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
                {
                    "id": "vector",
                    "href": "/icons/app.svg",
                    "mediaType": "image/svg+xml",
                    "sizes": ["any"],
                    "purposes": ["any"],
                },
                {
                    "id": "raster-192",
                    "href": "/icons/app-192.png",
                    "mediaType": "image/png",
                    "sizes": ["192x192"],
                    "purposes": ["any"],
                },
                {
                    "id": "raster-512",
                    "href": "/icons/app-512.png",
                    "mediaType": "image/png",
                    "sizes": ["512x512"],
                    "purposes": ["any"],
                },
                {
                    "id": "maskable-512",
                    "href": "/icons/app-maskable-512.png",
                    "mediaType": "image/png",
                    "sizes": ["512x512"],
                    "purposes": ["maskable"],
                },
            ],
            "vectorIconPolicy": "prefer-svg-when-compatible",
            "vectorIconException": None,
            "platformCompatibility": {
                "android": {
                    "requiredRasterSizes": ["192x192", "512x512"],
                    "maskableIconRequired": True,
                },
                "ios": {
                    "homeScreenIcon": {
                        "relation": "apple-touch-icon",
                        "href": "/icons/apple-touch-icon.png",
                        "mediaType": "image/png",
                        "sizes": ["180x180"],
                    }
                },
            },
        }
        offline = {
            "$schema": "../schemas/pwa-offline.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "availability": "offline-capable",
            "serviceWorkerScope": "/",
            "controlledRouteIds": ["home"],
            "navigationFallbackRouteId": "home",
            "networkUnavailableStateId": "network-unavailable",
            "freshnessUnknownStateId": "freshness-unverified",
            "revalidatingStateId": "revalidating",
            "surfacePolicies": [
                {
                    "surfaceId": "primary",
                    "cacheableDataClassifications": ["public"],
                }
            ],
            "cacheStrategy": "implementation-defined",
            "onlineFreshnessPolicy": "revalidate-before-display",
            "offlineFreshnessPolicy": "indicate-unverified",
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
        self.assertEqual(descriptor["version"], 3)
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
            errors = list(Draft202012Validator(self.load(f"schemas/{name}.schema.json")).iter_errors(document))
            self.assertEqual(errors, [], [error.message for error in errors])

    def test_template_mode_does_not_require_webapp_cross_contract_documents(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name in ("pwa-manifest", "pwa-offline", "pwa-update"):
            self.write_json(root / "contracts" / f"{name}.json", self.load(f"contracts/{name}.json"))
        self.write_json(root / "contracts/implementation-evidence.json", {"mode": "template"})
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("template mode OK", result.stdout)

    def test_product_cross_contract_semantics_validate(self) -> None:
        manifest, offline, update = self.product_contracts()
        result = self.run_validator(manifest, offline, update)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("offline freshness", result.stdout)
        self.assertIn("platform compatibility", result.stdout)

    def test_planning_mode_uses_the_same_semantic_contract_with_planning_evidence(self) -> None:
        manifest, offline, update = self.product_contracts()
        for document in (manifest, offline, update):
            document["mode"] = "planning"
        result = self.run_validator(manifest, offline, update, evidence_mode="planning")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PWA planning installability", result.stdout)

    def test_cache_algorithm_is_not_a_contract_choice(self) -> None:
        _manifest, offline, _update = self.product_contracts()
        schema = self.load("schemas/pwa-offline.schema.json")
        concrete = copy.deepcopy(offline)
        concrete["cacheStrategy"] = "network-first"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(concrete)))
        legacy = copy.deepcopy(offline)
        legacy["surfacePolicies"][0]["readBehavior"] = "cache-first"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(legacy)))

    def test_selected_pwa_requires_offline_capability_and_freshness_semantics(self) -> None:
        _manifest, offline, _update = self.product_contracts()
        schema = self.load("schemas/pwa-offline.schema.json")
        network_only = copy.deepcopy(offline)
        network_only["availability"] = "network-only"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(network_only)))
        for required in (
            "networkUnavailableStateId",
            "freshnessUnknownStateId",
            "revalidatingStateId",
            "onlineFreshnessPolicy",
            "offlineFreshnessPolicy",
        ):
            incomplete = copy.deepcopy(offline)
            incomplete.pop(required)
            self.assertTrue(list(Draft202012Validator(schema).iter_errors(incomplete)), required)

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

    def test_sub_scoped_pwa_accepts_scope_root_and_nested_routes(self) -> None:
        manifest, offline, update = self.product_contracts()
        manifest["scope"] = "/app/"
        offline["serviceWorkerScope"] = "/app/"
        routes, surfaces, states = self.webapp_contracts()
        routes["routes"] = [
            {"id": "home", "path": "/app", "surface": "primary", "canonical": True, "deepLink": True},
            {"id": "dashboard", "path": "/app/dashboard", "surface": "primary", "canonical": True, "deepLink": True},
        ]
        offline["controlledRouteIds"] = ["home", "dashboard"]
        offline["navigationFallbackRouteId"] = "home"
        result = self.run_validator(
            manifest,
            offline,
            update,
            routes=routes,
            surfaces=surfaces,
            states=states,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_manifest_icon_ids_and_hrefs_are_rejected(self) -> None:
        manifest, offline, update = self.product_contracts()
        duplicate_id = copy.deepcopy(manifest["icons"][0])
        duplicate_id["href"] = "/icons/other.svg"
        manifest["icons"].append(duplicate_id)
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate PWA manifest icon id", result.stderr)

        manifest, offline, update = self.product_contracts()
        duplicate_href = copy.deepcopy(manifest["icons"][0])
        duplicate_href["id"] = "other-vector"
        manifest["icons"].append(duplicate_href)
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate PWA manifest icon href", result.stderr)

    def test_offline_navigation_fallback_must_exist_and_be_controlled(self) -> None:
        manifest, offline, update = self.product_contracts()
        offline["navigationFallbackRouteId"] = "unknown"
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references unknown route 'unknown'", result.stderr)

        manifest, offline, update = self.product_contracts()
        routes, surfaces, states = self.webapp_contracts()
        routes["routes"].append(
            {"id": "uncontrolled", "path": "/other", "surface": "primary", "canonical": True, "deepLink": True}
        )
        offline["navigationFallbackRouteId"] = "uncontrolled"
        result = self.run_validator(
            manifest,
            offline,
            update,
            routes=routes,
            surfaces=surfaces,
            states=states,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("navigation fallback route must be included in controlledRouteIds", result.stderr)

    def test_offline_cache_policy_must_follow_surface_data_classification_authority(self) -> None:
        manifest, offline, update = self.product_contracts()
        offline["surfacePolicies"][0]["cacheableDataClassifications"] = ["secret"]
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("undeclared data classifications", result.stderr)

    def test_connectivity_freshness_and_revalidation_states_are_global_and_distinct(self) -> None:
        manifest, offline, update = self.product_contracts()
        _routes, surfaces, states = self.webapp_contracts()
        states["states"][0]["scope"] = "route"
        states["states"][2]["category"] = "content"
        offline["freshnessUnknownStateId"] = offline["networkUnavailableStateId"]
        result = self.run_validator(
            manifest,
            offline,
            update,
            surfaces=surfaces,
            states=states,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have global scope", result.stderr)
        self.assertIn("revalidatingStateId", result.stderr)
        self.assertIn("must use distinct UI state ids", result.stderr)

    def test_svg_is_preferred_but_a_reasoned_exception_is_allowed(self) -> None:
        manifest, offline, update = self.product_contracts()
        manifest["icons"] = [icon for icon in manifest["icons"] if icon["mediaType"] != "image/svg+xml"]
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declare an SVG manifest icon or a non-blank vectorIconException", result.stderr)
        manifest["vectorIconException"] = "The source artwork cannot be represented safely as SVG."
        result = self.run_validator(manifest, offline, update)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_android_and_ios_compatibility_intent_fails_closed(self) -> None:
        manifest, offline, update = self.product_contracts()
        manifest["icons"] = [icon for icon in manifest["icons"] if "192x192" not in icon["sizes"]]
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Android compatibility raster size '192x192'", result.stderr)

        manifest, offline, update = self.product_contracts()
        for icon in manifest["icons"]:
            icon["purposes"] = ["any"]
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("maskable manifest icon", result.stderr)

        manifest, offline, update = self.product_contracts()
        manifest["platformCompatibility"]["ios"]["homeScreenIcon"]["mediaType"] = "image/svg+xml"
        result = self.run_validator(manifest, offline, update)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("iOS home-screen compatibility icon", result.stderr)

    def test_update_schema_matches_activation_state_semantics(self) -> None:
        schema = self.load("schemas/pwa-update.schema.json")
        validator = Draft202012Validator(schema)
        _manifest, _offline, update = self.product_contracts()
        next_launch = copy.deepcopy(update)
        next_launch["activation"] = "next-launch"
        self.assertTrue(list(validator.iter_errors(next_launch)))
        next_launch.pop("updateAvailableStateId")
        self.assertEqual(list(validator.iter_errors(next_launch)), [])

        immediate = copy.deepcopy(next_launch)
        immediate["activation"] = "immediate"
        immediate["unsavedChangesPolicy"] = "block-activation"
        self.assertTrue(list(validator.iter_errors(immediate)))

    def test_update_states_have_global_semantic_category_floors(self) -> None:
        manifest, offline, update = self.product_contracts()
        _routes, surfaces, states = self.webapp_contracts()
        states["states"][6]["scope"] = "route"
        states["states"][6]["category"] = "content"
        result = self.run_validator(
            manifest,
            offline,
            update,
            surfaces=surfaces,
            states=states,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("applyingStateId", result.stderr)
        self.assertIn("global scope", result.stderr)

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
