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
                with self.assertRaisesRegex(ValueError, 'source identity changed'):
                    capsule.stage(
                        'build',
                        lambda: self.fail('cache hit must not execute the operation'),
                        validate_reuse=lambda: (_ for _ in ()).throw(ValueError('source identity changed')),
                    )
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

    def test_result_write_does_not_follow_legacy_temporary_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = Capsule(root / 'capsules', {'exact': 'input'})
            outside = root / 'outside.json'
            outside.write_text('protected')
            (capsule.root / 'result.tmp').symlink_to(outside)
            capsule.write({'schema_version': 1, 'inputs': capsule.inputs, 'stages': {}})
            self.assertEqual('protected', outside.read_text())
            self.assertTrue((capsule.root / 'result.tmp').is_symlink())
            self.assertEqual({}, capsule.read()['stages'])

    def test_lock_binds_artifact_path_to_original_entry_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capsule = Capsule(root / 'capsules', {'exact': 'input'})
            original = root / 'original-entry'
            replacement = root / 'replacement-entry'
            replacement.mkdir()
            with capsule.locked():
                capsule.root.rename(original)
                replacement.rename(capsule.root)
                self.assertNotEqual(capsule.workspace, capsule.root)
                self.assertIsInstance(capsule.inherited_fd, int)
                pinned = capsule.artifact
                pinned.mkdir(parents=True)
                (pinned / 'index.html').write_text('original')
            self.assertEqual('original', (original / 'build/site/index.html').read_text())
            self.assertFalse((capsule.root / 'build/site/index.html').exists())

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

    def test_rejects_generated_directory_symlink_from_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / '.gitignore').write_text('generated/\n')
            (root / 'source.py').write_text('source')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(
                ['git', '-C', str(root), '-c', 'user.name=Fixture',
                 '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'],
                check=True,
            )
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'mutable.txt').write_text('mutable')
            (root / 'generated').symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'must not be a symlink'):
                source_identity(root)

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
