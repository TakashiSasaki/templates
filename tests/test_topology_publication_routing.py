import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TopologyPublicationRoutingTests(unittest.TestCase):
    def test_topology_pages_have_consistent_route_and_evidence_targets(self):
        routes = json.loads((ROOT / "contracts/routes.json").read_text())["routes"]
        evidence = json.loads((ROOT / "contracts/implementation-evidence.json").read_text())
        targets = {(r["target"].get("contractId"), r["target"].get("itemId")) for r in evidence["records"]}
        for identity in ("composition-topology-contract", "composition-repository-topology-architecture", "site-repository-topology-overview"):
            with self.subTest(identity=identity):
                self.assertEqual(sum(route["id"] == identity for route in routes), 1)
                self.assertIn(("site_structure", identity), targets)
                self.assertIn(("document_metadata", identity), targets)

if __name__ == "__main__":
    unittest.main()
