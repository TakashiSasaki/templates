from __future__ import annotations
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts.local_qualification_capsule import Capsule, source_identity


class LocalCapsuleTests(unittest.TestCase):
    def test_reuse_failure_and_artifact_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            capsule = Capsule(Path(directory), {'exact': 'input'})
            calls = []
            def build():
                calls.append('build')
                capsule.artifact.mkdir(parents=True, exist_ok=True)
                (capsule.artifact / 'index.html').write_text('built')
            with capsule.locked():
                capsule.stage('build', build)
                capsule.stage('build', build)
                self.assertEqual(calls, ['build'])
                def failed():
                    raise RuntimeError('browser environment')
                with self.assertRaises(RuntimeError):
                    capsule.stage('browser', failed, artifact=True)
                capsule.stage('build', build)
                self.assertEqual(calls, ['build'])
                capsule.stage('browser', lambda: calls.append('browser'), artifact=True)
                self.assertEqual(capsule.read()['stages']['browser']['attempt'], 2)
                with self.assertRaisesRegex(ValueError, 'modified capsule artifact'):
                    capsule.stage(
                        'audience-static',
                        lambda: (capsule.artifact / 'index.html').write_text('changed during check'),
                        artifact=True,
                    )
                self.assertEqual(capsule.read()['stages']['audience-static']['result'], 'failure')
                (capsule.artifact / 'index.html').write_text('tampered')
                with self.assertRaisesRegex(ValueError, 'modified capsule artifact'):
                    capsule.stage('browser', lambda: None, artifact=True)

    def test_metadata_mismatch_and_interrupted_stage_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            capsule = Capsule(Path(directory), {'exact': 'input'})
            capsule.write({'schema_version': 0, 'inputs': capsule.inputs, 'stages': {}})
            with self.assertRaises(ValueError):
                capsule.read()
            capsule.record.unlink()
            data = capsule.read()
            data['stages']['core'] = {'result': 'running', 'attempt': 1}
            capsule.write(data)
            capsule.stage('core', lambda: None)
            self.assertEqual(capsule.read()['stages']['core']['attempt'], 2)

    def test_rejects_symlinked_capsule_root_and_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.mkdir()
            (root / 'root-link').symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'capsule root'):
                Capsule(root / 'root-link', {'exact': 'input'})

            capsule_root = root / 'capsules'
            capsule_root.mkdir()
            entry = capsule_root / 'f68edb85b67d3173f60de888719c1b66ed38c4205e609b121de38d56b0a68260'
            entry.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'capsule entry'):
                Capsule(capsule_root, {'exact': 'input'})

    def test_same_sha_is_insufficient_for_dirty_untracked_and_generated_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
            (root / 'source.py').write_text('initial')
            (root / '.gitignore').write_text('generated/\n')
            git('add', 'source.py', '.gitignore')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
            original = source_identity(root)
            for name in ['source.py', 'untracked.py', 'generated/output.json']:
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text('changed')
                current = source_identity(root)
                self.assertEqual(original['revision'], current['revision'])
                self.assertNotEqual(original['files'], current['files'])
                original = current

    def test_contract_declared_ignored_input_participates_in_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'docs').mkdir()
            (root / 'docs' / 'publication-catalog.json').write_text(json.dumps({
                'schema_version': 3,
                'documents': [
                    {'id': 'home', 'source': 'materialized/home.md', 'optional': False, 'home': True},
                ],
                'assets': [],
            }))
            (root / '.gitignore').write_text('materialized/\n')
            subprocess.run(
                ['git', '-C', str(root), 'add', 'docs/publication-catalog.json', '.gitignore'],
                check=True,
            )
            subprocess.run(
                ['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture'],
                check=True,
            )
            before = source_identity(root)
            output = root / 'materialized' / 'home.md'
            output.parent.mkdir()
            output.write_text('generated')
            after = source_identity(root)

        self.assertEqual(before['revision'], after['revision'])
        self.assertNotEqual(before['files'], after['files'])

    def test_schema_v4_contract_input_participates_in_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'docs').mkdir()
            (root / 'docs' / 'publication-catalog.json').write_text(json.dumps({
                'schema_version': 4,
                'documents': [
                    {'id': 'home', 'source': 'README.md', 'optional': False, 'home': True},
                ],
                'assets': [
                    {'source': 'generated/input.json', 'destination': 'input.json',
                     'optional': False, 'source_kind': 'generated'},
                ],
            }))
            (root / 'README.md').write_text('home')
            (root / '.gitignore').write_text('generated/\n')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(
                ['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture'], check=True,
            )
            before = source_identity(root)
            output = root / 'generated' / 'input.json'
            output.parent.mkdir()
            output.write_text('generated')
            after = source_identity(root)

        self.assertEqual(before['revision'], after['revision'])
        self.assertNotEqual(before['files'], after['files'])
