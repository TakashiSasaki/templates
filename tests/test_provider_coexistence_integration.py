from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_provider_coexistence import _absolute_without_resolving, _snapshot


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/provider-coexistence.yml"
SOURCE_LOCK = ROOT / "publication-sources.json"
COMPOSITION_REVISION = "ef0b3f40fa72578523abb34d238d690823cea931"
POLICY_REVISION = "3388f2df6c59cf2466b114cc236dd1b512349dc7"


class ProviderCoexistenceIntegrationTests(unittest.TestCase):
    def test_site_locks_reviewed_coexistence_provider_merges(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(
            lock["publications"],
            {
                "composition": {"revision": COMPOSITION_REVISION},
                "policy": {"revision": POLICY_REVISION},
            },
        )

    def test_workflow_resolves_only_the_site_lock_and_uses_isolated_toolchains(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: Provider coexistence integration", workflow)
        self.assertIn("--lock site-source/publication-sources.json", workflow)
        self.assertIn("ref: ${{ steps.publication_refs.outputs.composition }}", workflow)
        self.assertIn("ref: ${{ steps.publication_refs.outputs.policy }}", workflow)
        self.assertIn("path: composition-source", workflow)
        self.assertIn("path: policy-source", workflow)
        self.assertIn(".venv-composition", workflow)
        self.assertIn(".venv-policy", workflow)
        self.assertIn("scripts/validate_provider_coexistence.py", workflow)
        self.assertIn(
            '--composition-revision "${{ steps.publication_refs.outputs.composition }}"',
            workflow,
        )
        self.assertIn(
            '--policy-revision "${{ steps.publication_refs.outputs.policy }}"',
            workflow,
        )
        self.assertNotIn("refs/heads/composition", workflow)
        self.assertNotIn("refs/heads/policy", workflow)
        self.assertNotIn("composition_ref", workflow)
        self.assertNotIn("policy_ref", workflow)
        self.assertNotIn("skill-source", workflow)
        self.assertNotIn("webapp-source", workflow)

    def test_executable_path_preserves_virtualenv_symlink_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "python-real"
            real.write_text("", encoding="utf-8")
            venv = root / "venv" / "bin"
            venv.mkdir(parents=True)
            link = venv / "python"
            link.symlink_to(real)

            absolute = _absolute_without_resolving(link)

            self.assertEqual(absolute, link)
            self.assertTrue(absolute.is_symlink())
            self.assertNotEqual(absolute, link.resolve())

    def test_snapshot_tracks_bytes_and_directory_membership_without_following_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".agent-policy").mkdir()
            (root / ".agent-policy" / "state.json").write_bytes(b"state\n")
            (root / ".agent-policy.lock").write_bytes(b"lock\n")
            (root / "outside").write_bytes(b"outside\n")
            (root / ".agent-policy" / "alias").symlink_to(root / "outside")

            snapshot = _snapshot(
                root,
                (".agent-policy.yml", ".agent-policy.lock", ".agent-policy"),
            )

            self.assertEqual(snapshot[".agent-policy.lock"], ("file", b"lock\n"))
            self.assertEqual(
                snapshot[".agent-policy/state.json"],
                ("file", b"state\n"),
            )
            self.assertEqual(snapshot[".agent-policy/alias"][0], "symlink")
            self.assertNotIn("outside", snapshot)


if __name__ == "__main__":
    unittest.main()
