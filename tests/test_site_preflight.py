from __future__ import annotations

import os
import argparse
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace

from scripts import run_site_preflight as preflight
from tests.publication_context import provider_root


ROOT = Path(__file__).resolve().parents[1]


class SitePreflightTests(unittest.TestCase):
    def test_profiles_cover_owned_validation_and_exact_candidate_integration(self) -> None:
        self.assertEqual(
            ("reference-projections", "website-contract", "focused-tests"),
            preflight.PROFILES["fast"],
        )
        self.assertIn("unit-tests", preflight.PROFILES["full"])
        self.assertIn("node-explainability", preflight.PROFILES["full"])
        self.assertIn("cross-binding", preflight.PROFILES["full"])
        self.assertIn("candidate-projection", preflight.PROFILES["full"])
        self.assertEqual(
            ("cross-binding", "candidate-projection", "provider-tests", "cross-assembly"),
            preflight.PROFILES["cross"],
        )

    def test_blocking_workflows_delegate_to_named_preflight_checks(self) -> None:
        workflows = {
            "publication-materialization.yml": "--check materialization-tests",
            "publication-contract-v4.yml": "--check publication-contract-tests",
            "site-composition-playground-explain.yml": "--check node-explainability",
            "site-composition-playground-cross-authority.yml": "--check candidate-projection",
        }
        producer=(ROOT/'.github/workflows/site-producer.yml').read_text()
        self.assertIn('scripts/run_core_tests.py --suite core',producer)
        self.assertIn('./.github/workflows/integration-qualification.yml',producer)
        for name, expected in workflows.items():
            with self.subTest(name=name):
                text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn("run_site_preflight.py", text)
                self.assertIn(expected, text)

    def test_explicit_provider_root_is_validated_and_never_silently_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/publication-catalog.json").write_text("{}")
            with patch.dict(os.environ, {"SITE_COMPOSITION_ROOT": str(root)}):
                self.assertEqual(root.resolve(), provider_root("composition", ROOT))
            with patch.dict(os.environ, {"SITE_COMPOSITION_ROOT": ""}):
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    provider_root("composition", ROOT)

    def test_exact_candidate_workflow_has_no_literal_candidate_or_continue_on_error(self) -> None:
        text = (
            ROOT
            / ".github/workflows/site-composition-playground-cross-authority.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("resolve_publication_sources.py", text)
        self.assertTrue(
            "needs.resolve_candidate.outputs.composition_revision" in text
            or "needs.classify.outputs.composition_revision" in text
        )
        self.assertNotIn("continue-on-error", text)

    def test_cross_binding_dispatches_schema_v4_to_source_phase_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('composition', 'policy'):
                provider = root / name
                (provider / 'docs').mkdir(parents=True)
                (provider / 'docs' / 'publication-catalog.json').write_text(
                    '{"schema_version":4,"documents":[{"id":"home","source":"README.md","optional":false,"home":true}],"assets":[]}'
                )
                (provider / 'README.md').write_text('home')
            (root / 'publication-sources.json').write_text('{}')
            calls = []
            with patch.object(preflight, 'ROOT', root), \
                 patch.object(preflight, 'require_provider_roots', return_value=(root / 'composition', root / 'policy')), \
                 patch.object(preflight, 'resolve_sources', return_value={}), \
                 patch.object(preflight, 'git_head', return_value='revision'), \
                 patch.object(preflight, 'run', side_effect=lambda *args: calls.append(args)):
                preflight.check_cross_binding(object())
            validators = [call for call in calls if 'scripts/publication_contract_v4.py' in call]
            self.assertEqual(2, len(validators))
            self.assertTrue(all('--phase' in call and 'source' in call for call in validators))

    def test_capsule_workspace_consumers_inherit_the_locked_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            from scripts.local_qualification_capsule import Capsule

            capsule = Capsule(Path(directory), {'exact': 'input'})
            args = argparse.Namespace(capsule=capsule, composition_root=None, policy_root=None)
            with capsule.locked(), patch.object(preflight.subprocess, 'run') as run:
                run.return_value.returncode = 0
                preflight.run('consumer', args=args)
                descriptor = capsule.inherited_fd
                self.assertEqual((descriptor,), run.call_args.kwargs['pass_fds'])

    def test_cached_stage_uses_an_identity_checked_source_snapshot(self) -> None:
        from scripts.local_qualification_capsule import Capsule, input_identity

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roots = {}
            for name in ('site', 'composition', 'policy'):
                source = root / name
                source.mkdir()
                (source / 'source.txt').write_text(name)
                (source / '.gitignore').write_text('unbound/\n')
                if name == 'site':
                    (source / 'requirements-build.lock').write_text('')
                subprocess.run(['git', 'init', '-q', str(source)], check=True)
                subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
                subprocess.run(
                    ['git', '-C', str(source), '-c', 'user.name=Fixture',
                     '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'],
                    check=True,
                )
                roots[name] = source
            (roots['site'] / 'unbound').mkdir()
            (roots['site'] / 'unbound' / 'ignored.txt').write_text('not an identity input')
            capsule = Capsule(root / 'capsules', input_identity(roots))
            args = argparse.Namespace(
                capsule=capsule,
                capsule_roots=roots,
                composition_root=roots['composition'],
                policy_root=roots['policy'],
            )
            original_root = preflight.ROOT
            with capsule.locked(), preflight.capsule_source_snapshot(args, 'focused-tests'):
                self.assertNotEqual(preflight.ROOT, original_root)
                self.assertEqual('site', (preflight.ROOT / 'source.txt').read_text())
                self.assertFalse((preflight.ROOT / 'unbound' / 'ignored.txt').exists())
                (preflight.ROOT / 'source.txt').write_text('snapshot-only')
            self.assertEqual(original_root, preflight.ROOT)
            self.assertEqual('site', (roots['site'] / 'source.txt').read_text())


if __name__ == "__main__":
    unittest.main()

class CapabilityPrecheckTests(unittest.TestCase):
    def test_unknown_and_authority_changes_select_complete_core(self):
        from scripts.run_site_preflight import focused_tests
        for paths in ([], ['unknown.bin'], ['.github/workflows/build-pages.yml'], ['../escape']):
            with self.subTest(paths=paths):
                self.assertEqual(focused_tests(paths), ())

    def test_publication_change_reaches_real_consumer_and_sibling_boundaries(self):
        from scripts.run_site_preflight import focused_tests
        selected = focused_tests(['site-manifest.json'])
        self.assertIn('tests.test_audience_artifact_integration', selected)
        self.assertIn('tests.test_optional_document_source_type', selected)

class CapsuleInputRaceTests(unittest.TestCase):
    def test_input_mutation_before_cached_stage_is_rejected(self):
        capsule = Mock(inputs={'source':'old'})
        args = SimpleNamespace(capsule=capsule, capsule_roots={}, profile='ready')
        with patch('scripts.local_qualification_capsule.input_identity', return_value={'source':'new'}):
            self.assertEqual(preflight.execute_checks(args, ['audience-static'], 'head'), 1)
        capsule.stage.assert_not_called()
