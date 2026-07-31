from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


class ContractValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = validate_contracts.load_contract_documents(ROOT)

    def test_repository_contracts_are_valid(self) -> None:
        self.assertEqual([], validate_contracts.validate_repository(ROOT))

    def test_unknown_route_surface_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["routes"]["routes"][0]["surface"] = "missing-surface"
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("unknown surface missing-surface" in error for error in errors))

    def test_surface_dependency_cycle_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        surfaces = documents["surfaces"]["surfaces"]
        surfaces[0]["startupDependencies"] = [surfaces[1]["id"]]
        surfaces[1]["startupDependencies"] = [surfaces[0]["id"]]
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("dependency cycle" in error for error in errors))

    def test_viewport_gap_is_rejected(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["viewports"]["viewports"][1]["minWidthPx"] = 800
        errors = validate_contracts.cross_validate(documents)
        self.assertTrue(any("viewport boundary compact -> regular: gap" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
