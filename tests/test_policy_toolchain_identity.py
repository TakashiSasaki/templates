"""The required Policy Action executes the toolchain selected by Site."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class PolicyToolchainIdentityTests(unittest.TestCase):
    def test_required_action_matches_selected_immutable_policy(self):
        config = yaml.safe_load((ROOT / '.agent-policy.yml').read_text())
        workflow = yaml.safe_load((ROOT / '.github/workflows/check-agent-policy.yml').read_text())
        revision = config['toolchain']['revision']
        self.assertRegex(revision, r'^[0-9a-f]{40}$')
        actions = [step['uses'] for job in workflow['jobs'].values()
                   for step in job.get('steps', [])
                   if step.get('uses', '').startswith('TakashiSasaki/templates@')]
        self.assertEqual(actions, ['TakashiSasaki/templates@' + revision])
