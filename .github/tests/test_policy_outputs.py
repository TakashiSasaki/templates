"""Exercise Site review-output freshness with the installed, pinned Policy runtime."""
import shutil
import tempfile
import unittest
from pathlib import Path

from agent_policy.commands.check import run as check
from agent_policy.commands.render import run as render

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ".review-authority/review-policy.md"


class PolicyOutputTests(unittest.TestCase):
    def test_review_projection_is_checked_and_regenerated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "consumer"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            self.assertEqual(check(root, ".agent-policy.yml"), [])
            output = root / REVIEW
            original = output.read_bytes()
            for mutation in ("stale", "missing"):
                with self.subTest(mutation=mutation):
                    if mutation == "stale":
                        output.write_bytes(original + b"\nUnrendered change\n")
                    else:
                        output.unlink()
                    diagnostics = check(root, ".agent-policy.yml")
                    self.assertTrue(any(d.code == "STALE_OUTPUT" and d.path == REVIEW for d in diagnostics), diagnostics)
                    self.assertEqual(render(root, ".agent-policy.yml"), [])
                    self.assertEqual(output.read_bytes(), original)
                    self.assertEqual(check(root, ".agent-policy.yml"), [])
            with (root / "policy/project.md").open("a") as handle:
                handle.write("\n\nA repository-local normative change for freshness acceptance.\n")
            diagnostics = check(root, ".agent-policy.yml")
            self.assertTrue(any(d.code == "STALE_OUTPUT" and d.path == REVIEW for d in diagnostics), diagnostics)
            self.assertEqual(render(root, ".agent-policy.yml"), [])
            self.assertIn("repository-local normative change", output.read_text())
            self.assertEqual(check(root, ".agent-policy.yml"), [])


if __name__ == "__main__":
    unittest.main()
