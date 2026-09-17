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
                self.assertIn("inputs.browser_required == 'true'", workflow(file)['jobs'][job]['if'])

    def test_explainability_and_browser_are_distinct_required_suites(self):
        jobs = workflow('site-composition-playground-explain.yml')['jobs']
        self.assertIn('outputs.playground_required', jobs['explainability']['if'])
        self.assertIn('outputs.browser_required', jobs['browser']['if'])
        cheap = str(jobs['explainability']['steps'])
        self.assertIn('run_site_preflight.py fast --check node', cheap)
        self.assertNotIn('check_composition_playground_browser.py', cheap)
        for job in ['explainability', 'browser']:
            self.assertTrue(any(s.workflow_path.endswith('build-pages.yml') and s.job_name == 'explainability / ' + jobs[job]['name'] for s in REQUIRED_SUITES))

    def test_playground_workflows_use_the_canonical_node_inventory(self):
        for filename in ('site-composition-playground.yml', 'site-composition-playground-explain.yml'):
            with self.subTest(workflow=filename):
                text = (ROOT / '.github/workflows' / filename).read_text()
                self.assertIn('run_site_preflight.py fast --check node', text)
                self.assertNotIn('node --test tests/composition-playground', text)
                self.assertNotIn('node-explainability', text)
        self.assertIn('check_python_dependencies.py . --environment visual', (ROOT / '.github/workflows/site-composition-playground-explain.yml').read_text())
        playground = (ROOT / '.github/workflows/site-composition-playground.yml').read_text()
        self.assertNotIn('Validate Site integration declarations', playground)
        for shell_assertion in ('python -m json.tool', 'grep --fixed-strings', 'data-provenance-url'):
            self.assertNotIn(shell_assertion, playground)

    def test_website_contract_workflow_runs_the_repository_validator(self):
        website = str(workflow('validate-website.yml')['jobs']['validate-website']['steps'])
        self.assertIn('.template-composition/validate.py .', website)
        build_contract = str(workflow('build-pages.yml')['jobs']['website_contract']['steps'])
        self.assertIn('scripts/validate_website_contracts.py .', build_contract)
        self.assertIn('scripts/validate_site_declarations.py .', build_contract)
        self.assertIn('scripts/check_python_dependencies.py .', build_contract)
        self.assertIn('check_python_dependencies.py . --environment visual', str(workflow('build-pages.yml')['jobs']['check']['steps']))
        self.assertIn('.template-composition/validate.py .', build_contract)

    def test_browser_escalation_is_handled_at_every_browser_consumer(self):
        classifier_text = (ROOT / '.github/workflows/classify.yml').read_text()
        self.assertIn('--force-browser', classifier_text)
        self.assertIn('force_full=true', classifier_text)
        self.assertIn('git show "$BASE_SHA:scripts/classify_site_ci.py"', classifier_text)
        dispatcher = workflow('build-pages.yml')
        self.assertIn("github.event.label.name != 'ci/browser'", dispatcher['concurrency']['group'])
        for name in ('reference_consumer', 'cross_authority'):
            self.assertIn('needs.classify_browser.outputs.browser_required', dispatcher['jobs'][name]['with']['browser_required'])

    def test_exact_candidate_build_is_unique_and_browser_or_cross_authority_conditional(self):
        jobs=workflow('build-pages.yml')['jobs']
        self.assertEqual(jobs['build']['uses'],'./.github/workflows/site-producer.yml')
        self.assertIn('build',jobs['cross_authority']['needs'])
        worker=workflow('site-composition-playground-cross-authority.yml')['jobs']
        self.assertEqual(set(worker),{'producer_consumer'})
        self.assertIn('consume_site_build_artifact.py',str(worker['producer_consumer']['steps']))
        self.assertIn('--from-bundle',str(worker['producer_consumer']['steps']))
        self.assertNotIn('composition-source',str(worker))
        self.assertNotIn('resolve_publication_sources',str(worker))

    def test_safety_nets(self):
        # PyYAML's YAML 1.1 loader represents unquoted 'on' as True.
        events = workflow('build-pages.yml')[True]
        self.assertIn('schedule', events)
        self.assertIn('workflow_dispatch', events)
        self.assertFalse((ROOT/'.github/workflows/composition-real-browser.yml').exists())
        self.assertFalse((ROOT/'.github/workflows/mobile-visual-regression.yml').exists())

class FullStackTriggerTests(unittest.TestCase):
    def test_qualification_workflow_does_not_reintroduce_branch_allowlists(self):
        for suite in REQUIRED_SUITES:
            events=workflow(suite.workflow_path.rsplit('/',1)[1])[True]['pull_request']
            if events and 'branches' in events:
                self.fail(f"unexpected finite branch allowlist in {suite.workflow_path}")
