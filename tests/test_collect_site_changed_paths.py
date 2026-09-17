from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.collect_site_changed_paths import (
    BASE_UNAVAILABLE,
    DIFF_UNAVAILABLE,
    NON_SITE,
    collect,
)


class CollectSiteChangedPathsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def site_base(self) -> str:
        (self.root / ".github/workflows").mkdir(parents=True)
        (self.root / ".github/workflows/build-pages.yml").write_text("site\n")
        (self.root / "scripts").mkdir()
        (self.root / "scripts/classify_site_ci.py").write_text("# classifier\n")
        return self.commit("site base")

    def test_readable_site_base_collects_paths(self) -> None:
        base = self.site_base()
        (self.root / "docs.md").write_text("changed\n")
        head = self.commit("change")
        output = self.root / "paths.txt"

        self.assertEqual(0, collect(self.root, base, head, output))
        self.assertEqual("docs.md\n", output.read_text())

    def test_readable_non_site_base_is_not_a_site_candidate(self) -> None:
        (self.root / "README.md").write_text("base\n")
        base = self.commit("non-site base")
        (self.root / "docs.md").write_text("change\n")
        head = self.commit("change")

        self.assertEqual(
            NON_SITE,
            collect(self.root, base, head, self.root / "paths.txt"),
        )

    def test_unreadable_base_is_distinct_from_empty_input(self) -> None:
        head = self.site_base()

        self.assertEqual(
            BASE_UNAVAILABLE,
            collect(self.root, "0" * 40, head, self.root / "paths.txt"),
        )

    def test_diff_failure_is_distinct_from_empty_input(self) -> None:
        base = self.site_base()

        self.assertEqual(
            DIFF_UNAVAILABLE,
            collect(self.root, base, "0" * 40, self.root / "paths.txt"),
        )

    def test_valid_empty_diff_writes_empty_path_file(self) -> None:
        base = self.site_base()
        output = self.root / "paths.txt"

        self.assertEqual(0, collect(self.root, base, base, output))
        self.assertEqual("", output.read_text())


if __name__ == "__main__":
    unittest.main()
