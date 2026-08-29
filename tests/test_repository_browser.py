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
    BRANCH_ORDER as BASE_BRANCH_ORDER,
    MAX_TEXT_BYTES,
    RepositoryBrowserError,
    decode_browser_text,
    generate_browser,
    prepare_browser_root,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
PUBLIC_URL_BOUNDARY_CHECKER = ROOT / "scripts/check_public_url_boundary.py"
POLICY = ROOT / "PUBLISHING.md"
REQUIREMENTS = ROOT / "requirements.txt"
COMPOSITION_BROWSER_SCRIPT = (
    ROOT / "scripts" / "generate_repository_browser_composition.py"
)


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class RepositoryBrowserSafetyTests(unittest.TestCase):
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

    def test_base_renderer_preserves_bounded_sandboxed_source_views(self) -> None:
        self.assertEqual(BASE_BRANCH_ORDER, ("site", "composition", "policy"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)

            branches = {branch: repository for branch in BASE_BRANCH_ORDER}
            messages = generate_browser(
                "TakashiSasaki/templates", output, branches
            )

            self.assertEqual(len(messages), len(BASE_BRANCH_ORDER))
            self.assertTrue((output / "files/index.html").is_file())
            self.assertTrue((output / "files/site").is_dir())
            self.assertTrue((output / "files/composition").is_dir())
            self.assertTrue((output / "files/policy").is_dir())
            self.assertFalse((output / "files/skill").exists())
            self.assertFalse((output / "files/webapp").exists())
            root_index = (output / "files/index.html").read_text(encoding="utf-8")
            self.assertIn("Site, Composition, and Policy authorities", root_index)
            page = (output / "files/site/index.html").read_text(encoding="utf-8")
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
            self.assertIn("Content-Security-Policy", combined)
            self.assertIn(
                ".line-number { grid-column: 1; position: sticky;",
                combined,
            )
            self.assertIn(
                ".line-code { display: block; grid-column: 2;",
                combined,
            )
            self.assertIn(
                "#show-lines:not(:checked) ~ main .source-line { "
                "grid-template-columns: minmax(0, 1fr); }",
                combined,
            )
            self.assertIn(
                "#show-lines:not(:checked) ~ main .line-code { grid-column: 1; }",
                combined,
            )
            self.assertNotIn(
                "grid-template-columns: 0 minmax(0, 1fr)",
                combined,
            )

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
            branches = {branch: repository for branch in BASE_BRANCH_ORDER}
            with mock.patch.object(repository_browser, "MAX_TOTAL_TEXT_BYTES", 1):
                with self.assertRaisesRegex(
                    RepositoryBrowserError,
                    "text candidates exceed",
                ):
                    generate_browser("TakashiSasaki/templates", output, branches)


class CurrentAuthorityRepositoryBrowserTests(unittest.TestCase):
    def make_repository(self, root: Path) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Repository browser tests")
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def test_compat_entrypoint_delegates_to_canonical_authorities(self) -> None:
        wrapper = COMPOSITION_BROWSER_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("BRANCH_ORDER =", wrapper)
        self.assertNotIn("def write_root_index", wrapper)
        self.assertIn("return base.main()", wrapper)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)
            command = [
                sys.executable,
                str(COMPOSITION_BROWSER_SCRIPT),
                "--repository",
                "TakashiSasaki/templates",
                "--output-root",
                str(output),
            ]
            for branch in ("site", "composition", "policy"):
                command.extend(("--branch", f"{branch}={repository}"))
            result = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "files/site/index.html").is_file())
            self.assertTrue((output / "files/composition/index.html").is_file())
            self.assertTrue((output / "files/policy/index.html").is_file())
            self.assertFalse((output / "files/skill").exists())
            self.assertFalse((output / "files/webapp").exists())

    def test_workflow_uses_composition_browser_after_static_build(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        boundary_checker = PUBLIC_URL_BOUNDARY_CHECKER.read_text(encoding="utf-8")
        static_build = workflow.index("- name: Build the static site")
        browser_build = workflow.index("- name: Generate static repository browser")
        link_validation = workflow.index("- name: Validate generated site links")
        self.assertLess(static_build, browser_build)
        self.assertLess(browser_build, link_validation)
        self.assertIn("generate_repository_browser_composition.py", workflow)
        self.assertIn("--branch site=site-source", workflow)
        self.assertIn("--branch composition=composition-source", workflow)
        self.assertIn("--branch policy=policy-source", workflow)
        self.assertNotIn("--branch skill=", workflow)
        self.assertNotIn("--branch webapp=", workflow)
        self.assertIn("build/site/files/${branch}/index.html", workflow)
        self.assertIn("scripts/check_public_url_boundary.py", workflow)
        self.assertIn("browser_source_view", boundary_checker)
        self.assertIn("URLAttributeParser", boundary_checker)

    def test_policy_and_dependencies_preserve_browser_safety_boundary(self) -> None:
        policy = " ".join(POLICY.read_text(encoding="utf-8").split())
        requirements = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn("bounded build-time views", policy)
        self.assertIn("Symlinks and gitlinks are never followed", policy)
        self.assertIn("Site, Composition, and Policy", policy)
        self.assertIn("Pygments==", requirements)


if __name__ == "__main__":
    unittest.main()
