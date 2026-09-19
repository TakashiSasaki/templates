"""The maintainer landing route requires an explicit immutable gate closure."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MaintainerGateClosureTests(unittest.TestCase):
    def test_gate_closes_profile_rules_and_references(self):
        source = json.loads((ROOT / ".agents/skills/pr-merge-gate/source.json").read_text())
        self.assertEqual(source["schema_version"], 2)
        entries = source["closure"]
        paths = [entry["path"] for entry in entries]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn("profiles/pull-request.yml", paths)
        self.assertIn("policy/pull-request/independent-exact-head-review.md", paths)
        self.assertIn("skills/pr-merge-gate/references/review-acquisition-preflight.md", paths)
        for entry in entries:
            self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{40}", entry["blob_sha"]))
