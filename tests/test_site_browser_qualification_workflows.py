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
        self.assertIn('outputs.playground_required', jobs['explainability']['if'])
        self.assertIn('outputs.browser_required', jobs['browser']['if'])
        cheap = str(jobs['explainability']['steps'])
        self.assertIn('run_site_preflight.py fast --check node-explainability', cheap)
        self.assertNotIn('check_composition_playground_browser.py', cheap)
        for job in ['explainability', 'browser']:
            self.assertTrue(any(s.workflow_path.endswith('site-composition-playground-explain.yml') and s.job_name == jobs[job]['name'] for s in REQUIRED_SUITES))

    def test_browser_escalation_is_handled_at_every_browser_consumer(self):
        classifier_text = (ROOT / '.github/workflows/classify.yml').read_text()
        self.assertIn('--force-browser', classifier_text)
        self.assertIn('force_full=true', classifier_text)
        self.assertIn('git show "$BASE_SHA:scripts/classify_site_ci.py"', classifier_text)
        for name in ['build-pages.yml', 'reference-consumer.yml', 'site-composition-playground.yml', 'site-composition-playground-explain.yml', 'site-composition-playground-cross-authority.yml']:
            text = (ROOT / '.github/workflows' / name).read_text()
            with self.subTest(name=name):
                self.assertIn("github.event.label.name == 'ci/browser'", text)
                self.assertIn("github.event.label.name != 'ci/browser'", text)
                self.assertTrue(
                    "uses: ./.github/workflows/classify.yml" in text
                    or 'git show "$BASE_SHA:scripts/classify_site_ci.py"' in text
                )

    def test_exact_candidate_build_is_unique_and_conditional(self):
        jobs = workflow('site-composition-playground-cross-authority.yml')['jobs']
        self.assertIn(
            "needs.classify.outputs.cross_authority_required == 'true'",
            jobs['build_candidate']['if'],
        )
        self.assertEqual(
            1,
            sum(
                path.read_text().count('uses: ./.github/workflows/build-pages.yml')
                for path in (ROOT / '.github/workflows').glob('site-composition-*-cross-authority.yml')
            ),
        )

    def test_safety_nets(self):
        # PyYAML's YAML 1.1 loader represents unquoted 'on' as True.
        events = workflow('build-pages.yml')[True]
        self.assertIn('schedule', events)
        self.assertIn('workflow_dispatch', events)
        self.assertIn('schedule', workflow('composition-real-browser.yml')[True])
        self.assertEqual(set(workflow('mobile-visual-regression.yml')[True]), {'workflow_dispatch'})

class FullStackTriggerTests(unittest.TestCase):
    def test_all_filtered_qualification_workflows_cover_canonical_bases(self):
        canonical=set(workflow('build-pages.yml')[True]['pull_request']['branches'])
        for suite in REQUIRED_SUITES:
            events=workflow(suite.workflow_path.rsplit('/',1)[1])[True]['pull_request']
            if events and 'branches' in events:
                self.assertEqual(canonical,set(events['branches']),suite.workflow_path)
