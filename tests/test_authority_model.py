import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class AuthorityModelTests(unittest.TestCase):
    def test_discovery_uses_channel_without_committed_upstream_revision(self):
        agent=json.loads((ROOT/'agent.json').read_text())
        self.assertEqual(agent['integration_source'], {'channel':'publication-channel.json'})
        self.assertFalse((ROOT/'integration-source.json').exists())
