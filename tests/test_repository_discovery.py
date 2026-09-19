"""Required CI acceptance of the selected canonical discovery distribution."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryDiscoveryTests(unittest.TestCase):
    def require_clean(self, root):
        script = (root / '.agents/skills/maintain-progressive-discovery/scripts'
                  / 'maintain_progressive_discovery.py')
        result = subprocess.run(
            [sys.executable, str(script), '--root', str(root), '--format', 'json'],
            capture_output=True, text=True, check=False,
        )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, report['validation']['errors'])
        self.assertEqual(report['result'], 'NO_UPDATE_REQUIRED')

    def test_selected_repository_discovery_is_clean(self):
        self.require_clean(ROOT)

    def test_broken_navigation_fails_the_repository_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = subprocess.check_output(
                ['git', '-C', str(ROOT), 'ls-files', '-z']
            ).decode().split('\0')
            for relative in filter(None, paths):
                source = ROOT / relative
                if source.is_file():
                    destination = root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
            self.require_clean(root)
            index = root / 'index.md'
            index.write_text(index.read_text() + '\n- [Missing](missing-document.md)\n')
            with self.assertRaises(AssertionError):
                self.require_clean(root)
