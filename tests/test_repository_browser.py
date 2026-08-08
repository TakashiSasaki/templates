from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.generate_repository_browser as repository_browser
from scripts.generate_repository_browser import (
    BRANCH_ORDER,
    MAX_TEXT_BYTES,
    RepositoryBrowserError,
    decode_browser_text,
    generate_browser,
    prepare_browser_root,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
POLICY = ROOT / "PUBLISHING.md"
REQUIREMENTS = ROOT / "requirements.txt"
BROWSER_SCRIPT = ROOT / "scripts" / "generate_repository_browser.py"


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class RepositoryBrowserTests(unittest.TestCase):
    def make_repository(self, root: Path) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Repository browser tests")
        (root / "src").mkdir()
        (root / "src/example.py").write_text(
            "def answer():\n    return 42\n", encoding="utf-8"
        )
        (root / "README.md").write_text(
            "# Fixture\n\n<script>alert('escaped')</script>\n", encoding="utf-8"
        )
        (root / "binary.bin").write_bytes(b"\x00\x01\x02")
        os.symlink("README.md", root / "readme-link")
        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def test_generates_four_branch_tree_and_sandboxed_highlighted_viewers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)

            branches = {branch: repository for branch in BRANCH_ORDER}
            messages = generate_browser(
                "TakashiSasaki/templates", output, branches
            )

            self.assertEqual(len(messages), 4)
            self.assertTrue((output / "files/index.html").is_file())
            for branch in BRANCH_ORDER:
                page = (output / f"files/{branch}/index.html").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f"{branch} branch file browser", page)
                self.assertIn('name="repository-file-viewer"', page)
                self.assertIn('sandbox=""', page)
                self.assertIn("tree-file--fallback", page)
                self.assertIn('class="tree-source"', page)
                self.assertIn('target="_blank" rel="noopener"', page)
                self.assertNotIn("raw.githubusercontent.com", page)

            viewers = sorted((output / "files/site/content").glob("*.html"))
            self.assertEqual(len(viewers), 3)
            combined = "\n".join(
                path.read_text(encoding="utf-8") for path in viewers
            )
            self.assertIn("Line numbers", combined)
            self.assertIn("Wrap lines", combined)
            self.assertIn('class="line-number"', combined)
            self.assertIn("return", combined)
            self.assertIn(
                "&lt;script&gt;alert('escaped')&lt;/script&gt;",
                combined,
            )
            self.assertNotIn("<script>alert('escaped')</script>", combined)
            self.assertIn("Text view unavailable", combined)
            self.assertIn("source arrow beside the file name", combined)
            self.assertNotIn('target="_blank"', combined)
            self.assertIn("Content-Security-Policy", combined)

    def test_text_boundary_rejects_invalid_or_unsafe_content(self) -> None:
        self.assertEqual(decode_browser_text(b"hello\n"), ("hello\n", None))
        self.assertIsNone(decode_browser_text(b"\x00binary")[0])
        self.assertIsNone(decode_browser_text(b"\xff")[0])
        self.assertIsNone(decode_browser_text(b"escape\x1bsequence")[0])
        self.assertIsNone(
            decode_browser_text("left\u202eright".encode("utf-8"))[0]
        )
        text, reason = decode_browser_text(b"x" * (MAX_TEXT_BYTES + 1))
        self.assertIsNone(text)
        self.assertIn("browser limit", reason or "")

    def test_generation_rejects_out_of_order_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "site"
            output.mkdir()
            branches = {
                "skill": root,
                "site": root,
                "policy": root,
                "webapp": root,
            }
            with self.assertRaisesRegex(
                RepositoryBrowserError,
                "branches must be supplied exactly",
            ):
                generate_browser("TakashiSasaki/templates", output, branches)
            self.assertFalse((output / "files").exists())

    def test_prepare_browser_root_fails_closed_when_destination_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            browser_root = output / "files"
            browser_root.mkdir()
            (browser_root / ".repository-browser-root").write_text(
                "managed by scripts/generate_repository_browser.py\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RepositoryBrowserError,
                "browser destination already exists",
            ):
                prepare_browser_root(output)
            self.assertTrue(browser_root.is_dir())

    def test_total_candidate_budget_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)
            branches = {branch: repository for branch in BRANCH_ORDER}
            with mock.patch.object(
                repository_browser,
                "MAX_TOTAL_TEXT_BYTES",
                1,
            ):
                with self.assertRaisesRegex(
                    RepositoryBrowserError,
                    "text candidates exceed",
                ):
                    generate_browser("TakashiSasaki/templates", output, branches)

    def test_cli_rejects_duplicate_and_out_of_order_branch_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            duplicate = subprocess.run(
                [
                    sys.executable,
                    str(BROWSER_SCRIPT),
                    "--repository",
                    "TakashiSasaki/templates",
                    "--output-root",
                    str(output),
                    "--branch",
                    "site=unused",
                    "--branch",
                    "site=unused",
                    "--branch",
                    "skill=unused",
                    "--branch",
                    "policy=unused",
                    "--branch",
                    "webapp=unused",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("duplicate branch: site", duplicate.stderr)

            out_of_order = subprocess.run(
                [
                    sys.executable,
                    str(BROWSER_SCRIPT),
                    "--repository",
                    "TakashiSasaki/templates",
                    "--output-root",
                    str(output),
                    "--branch",
                    "skill=unused",
                    "--branch",
                    "site=unused",
                    "--branch",
                    "policy=unused",
                    "--branch",
                    "webapp=unused",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(out_of_order.returncode, 2)
            self.assertIn("branches must be supplied exactly", out_of_order.stderr)


class RepositoryBrowserConfigurationTests(unittest.TestCase):
    def test_workflow_builds_browser_after_zensical_and_before_link_validation(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        static_build = workflow.index("- name: Build the static site")
        browser_build = workflow.index("- name: Generate static repository browser")
        link_validation = workflow.index("- name: Validate generated site links")
        self.assertLess(static_build, browser_build)
        self.assertLess(browser_build, link_validation)
        self.assertIn("--branch site=site-source", workflow)
        self.assertIn("--branch skill=skill-source", workflow)
        self.assertIn("--branch policy=policy-source", workflow)
        self.assertIn("--branch webapp=webapp-source", workflow)
        self.assertIn("build/site/files/${branch}/index.html", workflow)
        self.assertIn("browser_source_view", workflow)
        self.assertIn("URLAttributeParser", workflow)

    def test_policy_and_dependencies_define_browser_boundary(self) -> None:
        policy = " ".join(POLICY.read_text(encoding="utf-8").split())
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn("Static file browser", policy)
        self.assertIn("1 MiB", policy)
        self.assertIn("64 MiB", policy)
        self.assertIn("Pygments", policy)
        self.assertIn("runtime GitHub API", policy)
        self.assertIn("Pygments==", requirements)


if __name__ == "__main__":
    unittest.main()
