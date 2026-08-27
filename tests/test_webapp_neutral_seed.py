from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "components" / "artifact.webapp-core"
FILES = WEBAPP / "files"


def load_json(relative: str) -> dict:
    return json.loads((FILES / relative).read_text(encoding="utf-8"))


class WebappNeutralSeedTests(unittest.TestCase):
    def test_fresh_seed_has_only_one_neutral_browser_surface_and_route(self) -> None:
        surfaces = load_json("contracts/surfaces.json")["surfaces"]
        routes = load_json("contracts/routes.json")["routes"]

        self.assertEqual([surface["id"] for surface in surfaces], ["primary"])
        self.assertEqual(
            surfaces[0],
            {
                "id": "primary",
                "title": "Primary browser surface",
                "purpose": (
                    "Provide the product's primary browser-facing experience without "
                    "assuming authentication, administration, or operational diagnostics."
                ),
                "audiences": ["anonymous"],
                "authentication": "none",
                "authorization": {"mode": "public", "roles": []},
                "dataClassifications": ["public"],
                "stability": "experimental",
                "surfaceDependencies": [],
                "diagnostic": False,
            },
        )
        self.assertEqual([route["id"] for route in routes], ["home"])
        self.assertEqual(routes[0]["path"], "/")
        self.assertEqual(routes[0]["surface"], "primary")
        self.assertEqual(routes[0]["authentication"], "none")
        self.assertEqual(routes[0]["authenticationReturn"], "not-applicable")
        self.assertEqual(
            routes[0]["accessFailures"],
            {
                "unauthenticated": {"behavior": "not-applicable"},
                "forbidden": {"behavior": "not-applicable"},
            },
        )
        self.assertEqual(routes[0]["states"], ["ready"])

    def test_fresh_seed_has_five_current_evidence_targets(self) -> None:
        states = load_json("contracts/ui-states.json")["states"]
        viewports = load_json("contracts/viewports.json")

        self.assertEqual([state["id"] for state in states], ["ready"])
        self.assertEqual(
            [(item["id"], item["minWidthPx"]) for item in viewports["viewports"]],
            [("base", 0)],
        )
        self.assertEqual(viewports["inputCapabilities"], ["keyboard"])

        target_count = (
            len(load_json("contracts/surfaces.json")["surfaces"])
            + len(load_json("contracts/routes.json")["routes"])
            + len(states)
            + len(viewports["viewports"])
            + len(viewports["inputCapabilities"])
        )
        self.assertEqual(target_count, 5)

    def test_seed_change_does_not_create_a_managed_upgrade_boundary(self) -> None:
        descriptor = json.loads((WEBAPP / "component.json").read_text(encoding="utf-8"))
        self.assertEqual(descriptor["version"], 13)
        seed_destinations = {
            material["destination"]
            for material in descriptor["materials"]
            if material["ownership"] == "seed"
        }
        self.assertTrue(
            {
                "contracts/surfaces.json",
                "contracts/routes.json",
                "contracts/ui-states.json",
                "contracts/viewports.json",
                "TEMPLATE.md",
            }
            <= seed_destinations
        )

    def test_worksheet_makes_product_owned_expansion_explicit(self) -> None:
        worksheet = (FILES / "TEMPLATE.md").read_text(encoding="utf-8")
        self.assertIn("deliberately minimal seeds", worksheet)
        self.assertIn("do not imply that the product needs authentication", worksheet)
        self.assertIn("provider history that predates the product", worksheet)
        self.assertIn("not a fresh-product implementation obligation", worksheet)


if __name__ == "__main__":
    unittest.main()
