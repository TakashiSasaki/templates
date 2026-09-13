"""Applicability and full-suite topology contracts across browser consumers."""
from pathlib import Path
import unittest
import yaml
from scripts.verify_site_full_qualification import REQUIRED_SUITES

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


class BrowserWorkflowTests(unittest.TestCase):
    def test_reference_and_cross_authority_do_not_inherit_build_applicability(self):
        for file, job in [('reference-consumer.yml', 'browser'), ('site-composition-playground-cross-authority.yml', 'producer_consumer')]:
            with self.subTest(file=file):
                self.assertIn("needs.classify.outputs.browser_required == 'true'", workflow(file)['jobs'][job]['if'])

    def test_explainability_and_browser_are_distinct_required_suites(self):
        jobs = workflow('site-composition-playground-explain.yml')['jobs']
        self.assertIn('outputs.required', jobs['explainability']['if'])
        self.assertIn('outputs.browser_required', jobs['browser']['if'])
        cheap = str(jobs['explainability']['steps'])
        self.assertIn('node --test', cheap)
        self.assertNotIn('check_composition_playground_browser.py', cheap)
        for job in ['explainability', 'browser']:
            self.assertTrue(any(s.workflow_path.endswith('site-composition-playground-explain.yml') and s.job_name == jobs[job]['name'] for s in REQUIRED_SUITES))

    def test_browser_escalation_is_handled_at_every_browser_consumer(self):
        for name in ['build-pages.yml', 'reference-consumer.yml', 'site-composition-playground.yml', 'site-composition-playground-explain.yml', 'site-composition-playground-cross-authority.yml']:
            text = (ROOT / '.github/workflows' / name).read_text()
            with self.subTest(name=name):
                self.assertIn("github.event.label.name == 'ci/browser'", text)
                self.assertIn("github.event.label.name != 'ci/browser'", text)
                self.assertIn('--force-browser', text)
                self.assertIn('force_full=true', text)
                self.assertIn('git show "$BASE_SHA:scripts/classify_site_ci.py"', text)

    def test_materialization_build_is_conditional(self):
        self.assertIn("needs.classify.outputs.required == 'true'", workflow('site-composition-materialization-cross-authority.yml')['jobs']['build_candidate']['if'])

    def test_safety_nets(self):
        # PyYAML's YAML 1.1 loader represents unquoted 'on' as True.
        events = workflow('build-pages.yml')[True]
        self.assertIn('schedule', events)
        self.assertIn('workflow_dispatch', events)
        self.assertIn('schedule', workflow('composition-real-browser.yml')[True])
        self.assertEqual(set(workflow('mobile-visual-regression.yml')[True]), {'workflow_dispatch'})
