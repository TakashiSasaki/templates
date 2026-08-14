from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_browser import BRANCH_ORDER, generate_browser


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class RepositoryBrowserMobileTests(unittest.TestCase):
    def make_repository(self, root: Path) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Repository browser mobile tests")
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def test_generated_browser_supports_progressive_full_height_mobile_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)

            generate_browser(
                "TakashiSasaki/templates",
                output,
                {branch: repository for branch in BRANCH_ORDER},
            )

            page = (output / "files/site/index.html").read_text(encoding="utf-8")
            self.assertIn(
                "grid-template-rows: minmax(16rem, 42vh) 58vh",
                page,
            )
            self.assertIn("repository-browser-enhanced", page)
            self.assertIn("height: 100dvh", page)
            self.assertIn('data-mobile-view="files"', page)
            self.assertIn("data-repository-tree", page)
            self.assertIn("data-repository-content", page)
            self.assertIn("data-show-files", page)
            self.assertIn("data-selected-file", page)
            self.assertIn('data-file-path="README.md"', page)
            self.assertIn('script-src \'self\'', page)
            self.assertIn(
                '<script src="../repository-browser.js" defer></script>',
                page,
            )
            self.assertEqual(page.count("<script"), 1)

            copied_controller = output / "files/repository-browser.js"
            self.assertTrue(copied_controller.is_file())
            self.assertEqual(
                copied_controller.read_text(encoding="utf-8"),
                CONTROLLER.read_text(encoding="utf-8"),
            )

    def test_controller_uses_explicit_navigation_without_swipe_or_history(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('matchMedia("(max-width: 800px)")', controller)
        self.assertIn('setMobileMode("content")', controller)
        self.assertIn('setMobileMode("files")', controller)
        self.assertIn("tree.inert", controller)
        self.assertIn("content.inert", controller)
        self.assertIn("preventScroll: true", controller)
        self.assertNotIn("touchstart", controller)
        self.assertNotIn("touchmove", controller)
        self.assertNotIn("pushState", controller)
        self.assertNotIn("popstate", controller)


if __name__ == "__main__":
    unittest.main()
