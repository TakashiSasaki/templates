"""Scheduling is a priority hint, never a new acceptance exemption."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import yaml
from scripts.classify_site_ci import classify_paths
from scripts.pwa_failure_evidence import attach, snapshot

ROOT = Path(__file__).resolve().parents[1]

class BrowserPriorityTests(unittest.TestCase):
    def test_priority_does_not_weaken_unknown_or_control_changes(self):
        for path, priority in [('assets/javascripts/audience.js', 'audience'),
                               ('assets/javascripts/search-history.js', 'search'),
                               ('assets/service-worker.js', 'pwa'),
                               ('stylesheets/extra.css', 'layout')]:
            with self.subTest(path=path):
                self.assertEqual(classify_paths([path]).browser_priority, priority)
                decision = classify_paths([path, 'unknown-authority.xyz'])
                self.assertTrue(decision.full_required)
                self.assertTrue(decision.browser_required)
                self.assertTrue(decision.pwa_required)

    def test_early_check_preserves_original_command_and_requires_observed_success(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/build-pages.yml').read_text())
        steps = workflow['jobs']['check']['steps']
        by_name = {s['name']: s for s in steps}
        originals = {'audience':'Check assembled audience runtime and navigation',
                     'search':'Check Site search history', 'pwa':'Check PWA freshness lifecycle',
                     'layout':'Check mobile layout geometry'}
        for key, name in originals.items():
            early = by_name[f'Check changed-feature {key}']
            later = by_name[name]
            self.assertEqual(early['run'], later['run'])
            self.assertIn(f"browser_priority == '{key}'", early['if'])
            self.assertIn("browser_required == 'true'", early['if'])
            self.assertIn(f"steps.priority_{key}.outcome != 'success'", later['if'])
            self.assertLess(steps.index(early), steps.index(by_name['Check mobile layout geometry']))
        self.assertLess(steps.index(by_name['Check assembled audience runtime and navigation']),
                        steps.index(by_name['Check PWA slow-network convergence']))

    def test_observation_is_bounded_and_snapshot_errors_remain_diagnostic(self):
        context = Mock()
        evidence = {}
        attach(context, evidence)
        callback = context.expose_binding.call_args.args[1]
        for i in range(510):
            callback({'page':SimpleNamespace(url='http://fixture/')}, {'kind':'statechange','n':i})
        self.assertEqual(len(evidence['lifecycle']),500)
        page=Mock(); page.is_closed.return_value=False; page.url='http://fixture/'
        page.evaluate.side_effect=RuntimeError('page terminated')
        context.pages=[page]
        snapshot(context,evidence)
        self.assertEqual(evidence['pages'][0]['snapshot_error'],'page terminated')
