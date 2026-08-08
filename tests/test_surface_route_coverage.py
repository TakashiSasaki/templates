from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class SurfaceRouteCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)

    def test_every_surface_requires_at_least_one_canonical_route(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["routes"]["routes"] = [
            route
            for route in documents["routes"]["routes"]
            if route["surface"] != "status"
        ]

        errors = validate_contracts.cross_validate(documents)

        self.assertIn("surface status: no canonical route declares this surface", errors)

    def test_multiple_canonical_routes_may_share_one_surface(self) -> None:
        documents = copy.deepcopy(self.documents)
        additional_route = copy.deepcopy(documents["routes"]["routes"][0])
        additional_route["id"] = "about"
        additional_route["path"] = "/about"
        documents["routes"]["routes"].append(additional_route)

        errors = validate_contracts.cross_validate(documents)

        self.assertFalse(
            any("surface public: no canonical route declares this surface" == error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
