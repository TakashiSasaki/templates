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
