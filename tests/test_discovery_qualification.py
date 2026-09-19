import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import qualify


class DiscoveryQualificationTests(unittest.TestCase):
    def test_qualification_rejects_stale_and_unreachable_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'modeling'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
            for arguments in (['init', '-q'], ['add', '.'], ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']):
                subprocess.run(['git', '-C', str(root), *arguments], check=True)
            qualify.check_progressive_discovery(root)
            adapter = root / '.progressive-discovery.json'
            original = adapter.read_text()
            data = json.loads(original)
            data['generated_indexes']['docs/resources/index.md']['title'] = 'Changed title'
            adapter.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'progressive discovery'):
                qualify.check_progressive_discovery(root)
            with patch.object(qualify, '__file__', str(root / 'tools/qualify.py')), patch.object(
                qualify.unittest.TestLoader, 'discover',
                return_value=unittest.TestSuite([unittest.FunctionTestCase(lambda: None)]),
            ):
                self.assertEqual(qualify.main(), 1)
            adapter.write_text(original)
            (root / 'index.md').unlink()
            with self.assertRaisesRegex(ValueError, 'progressive discovery'):
                qualify.check_progressive_discovery(root)
            with patch.object(qualify, '__file__', str(root / 'tools/qualify.py')), patch.object(
                qualify.unittest.TestLoader, 'discover',
                return_value=unittest.TestSuite([unittest.FunctionTestCase(lambda: None)]),
            ):
                self.assertEqual(qualify.main(), 1)

    def test_qualification_rejects_policy_distribution_drift_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'modeling'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
            cases = [
                '.agents/skills/maintain-progressive-discovery/SKILL.md',
                '.agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py',
                '.agent-policy.yml',
            ]
            for relative in cases:
                with self.subTest(relative=relative):
                    target = root / relative
                    original = target.read_bytes()
                    target.write_bytes(original + b'\n# drift\n')
                    with patch.object(qualify.subprocess, 'run') as execute:
                        with self.assertRaisesRegex(ValueError, 'Policy distribution'):
                            qualify.check_progressive_discovery(root)
                        execute.assert_not_called()
                    target.write_bytes(original)

    def test_qualification_rejects_invalid_policy_lock(self):
        import copy
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'modeling'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
            path = root / '.agent-policy.lock'
            original = yaml.safe_load(path.read_text())
            skill = '.agents/skills/maintain-progressive-discovery/SKILL.md'
            variants = []
            for key, value in [('revision', '0' * 40), ('repository', 'other/repository')]:
                changed = copy.deepcopy(original)
                changed['toolchain'][key] = value
                variants.append(changed)
            changed = copy.deepcopy(original)
            del changed['outputs'][skill]
            variants.append(changed)
            changed = copy.deepcopy(original)
            changed['outputs']['../outside'] = changed['outputs'].pop(skill)
            variants.append(changed)
            variants.extend([None, {'lock_version': True}])
            for variant in variants:
                with self.subTest(lock=variant):
                    path.write_text(yaml.safe_dump(variant))
                    with patch.object(qualify.subprocess, 'run') as execute:
                        with self.assertRaisesRegex(ValueError, 'Policy distribution'):
                            qualify.check_progressive_discovery(root)
                        execute.assert_not_called()
