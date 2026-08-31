from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "components" / "artifact.webapp-core"
FOUNDATION = ROOT / "components" / "foundation.web"
WEBAPP_FILES = WEBAPP / "files"
FOUNDATION_FILES = FOUNDATION / "files"

def load_json(base: Path, relative: str) -> dict:
    return json.loads((base / relative).read_text(encoding="utf-8"))

class WebappNeutralSeedTests(unittest.TestCase):
    def test_fresh_seed_separates_shared_route_from_application_behavior(self) -> None:
        shared = load_json(FOUNDATION_FILES, "contracts/routes.json")["routes"]
        application = load_json(WEBAPP_FILES, "contracts/application-routes.json")["routes"]
        self.assertEqual([route["id"] for route in shared], ["home"])
        self.assertEqual(set(shared[0]), {"id", "path", "canonical", "aliases", "deepLink", "accessibility"})
        self.assertEqual([route["routeId"] for route in application], ["home"])
        self.assertEqual(application[0]["surface"], "primary")
        self.assertEqual(application[0]["authentication"], "none")
        self.assertEqual(application[0]["states"], ["ready"])

    def test_fresh_seed_prefers_a_standard_svg_favicon(self) -> None:
        identity = load_json(FOUNDATION_FILES, "contracts/browser-identity.json")
        self.assertEqual(identity["favicon"]["relation"], "icon")
        self.assertEqual(identity["favicon"]["mediaType"], "image/svg+xml")

    def test_evidence_targets_include_application_route_behavior(self) -> None:
        source = (WEBAPP_FILES / "scripts" / "webapp_evidence_targets.py").read_text(encoding="utf-8")
        self.assertIn('"contractId": "application_routes"', source)
        self.assertIn('"itemKind": "application-route"', source)

    def test_foundation_is_required_but_not_a_direct_seed_selection(self) -> None:
        descriptor = json.loads((WEBAPP / "component.json").read_text(encoding="utf-8"))
        self.assertIn("foundation.web", descriptor["requires"])
        self.assertEqual(json.loads((FOUNDATION / "component.json").read_text(encoding="utf-8"))["component_role"], "foundation")

if __name__ == "__main__":
    unittest.main()
