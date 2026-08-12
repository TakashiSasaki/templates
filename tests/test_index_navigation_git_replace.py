from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import generate_index_navigation as navigation


def run_git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        input=input_bytes,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process.stdout


class GitReplaceBoundaryTests(unittest.TestCase):
    def test_reachable_index_reads_ignore_local_replace_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "provider"
            root.mkdir()
            run_git(root, "init", "--quiet")
            run_git(root, "config", "user.email", "tests@example.invalid")
            run_git(root, "config", "user.name", "Git replace review tests")
            (root / "docs").mkdir()
            (root / "docs/index.md").write_text("# Original docs\n", encoding="utf-8")
            run_git(root, "add", "docs/index.md")
            run_git(root, "commit", "--quiet", "--message", "fixture")

            object_id = run_git(root, "rev-parse", "HEAD:docs/index.md").decode().strip()
            replacement_id = run_git(
                root,
                "hash-object",
                "-w",
                "--stdin",
                input_bytes=b"# Replaced docs\n",
            ).decode().strip()
            run_git(root, "replace", object_id, replacement_id)

            self.assertEqual(
                run_git(root, "cat-file", "blob", object_id),
                b"# Replaced docs\n",
            )
            graph = navigation.collect_provider_graph("skill", root)
            self.assertEqual(graph["indexes"][0]["title"], "Original docs")
            self.assertEqual(graph["indexes"][0]["object_id"], object_id)


if __name__ == "__main__":
    unittest.main()
