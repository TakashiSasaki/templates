from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


def make_repository(root: Path) -> None:
    root.mkdir()
    run_git(root, "init", "--quiet")
    run_git(root, "config", "user.email", "tests@example.invalid")
    run_git(root, "config", "user.name", "Latest review tests")
    (root / "docs").mkdir()
    (root / "docs/index.md").write_text(
        "# Docs\n\n## Start\n\n* [Overview](overview.md) - Read it.\n",
        encoding="utf-8",
    )
    (root / "docs/overview.md").write_text("# Overview\n", encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "--quiet", "--message", "fixture")


def commit_root(root: Path, text: str, message: str) -> None:
    (root / "docs/index.md").write_text(text, encoding="utf-8")
    run_git(root, "add", "docs/index.md")
    run_git(root, "commit", "--quiet", "--message", message)


class LatestIndexNavigationReviewTests(unittest.TestCase):
    def test_directory_dot_markers_do_not_collapse_to_regular_files(self) -> None:
        for target in ("overview.md/.", "overview.md/%2E"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - Directory-marked file target.\n",
                    "directory marker",
                )
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "repository link targets a regular file",
                ):
                    navigation.collect_provider_graph("skill", repository)

    def test_repository_root_directory_resolves_root_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            (repository / "index.md").write_text(
                "# Repository root\n\n## Documentation\n\n"
                "* [Docs](docs/) - Return to provider docs.\n",
                encoding="utf-8",
            )
            commit_root(
                repository,
                "# Docs\n\n* [Repository root](../) - Follow the root index.\n",
                "link repository root",
            )
            run_git(repository, "add", "index.md")
            run_git(repository, "commit", "--quiet", "--message", "root index")

            graph = navigation.collect_provider_graph("skill", repository)

            self.assertIn("index.md", [item["path"] for item in graph["indexes"]])
            edge = next(
                item for item in graph["edges"] if item["label"] == "Repository root"
            )
            self.assertEqual(edge["kind"], "index")
            self.assertEqual(edge["target"], "index.md")

    def test_external_hosts_reject_whitespace_and_percent_encoding(self) -> None:
        for target in (
            "https://exa mple.com/path",
            "https://exa%20mple.com/path",
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - Invalid hostname.\n",
                    "bad host",
                )
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    navigation.collect_provider_graph("skill", repository)

    def test_non_utf8_unreachable_repository_path_is_ignored(self) -> None:
        if os.name == "nt":
            self.skipTest("byte-only POSIX filenames are not representable on Windows")
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            raw_root = os.fsencode(repository)
            raw_name = b"unreachable-\xff.txt"
            fd = os.open(raw_root + b"/" + raw_name, os.O_WRONLY | os.O_CREAT, 0o644)
            try:
                os.write(fd, b"unreachable\n")
            finally:
                os.close(fd)
            subprocess.run(
                [b"git", b"-C", raw_root, b"add", b"--", raw_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            run_git(repository, "commit", "--quiet", "--message", "byte-only path")

            graph = navigation.collect_provider_graph("skill", repository)

            self.assertEqual(graph["indexes"][0]["path"], "docs/index.md")

    def test_tree_listing_is_pinned_to_recorded_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            old_revision = run_git(repository, "rev-parse", "HEAD")
            commit_root(repository, "# New docs\n", "advance head")

            with mock.patch.object(
                navigation,
                "checked_revision",
                return_value=old_revision,
            ):
                graph = navigation.collect_provider_graph("skill", repository)

            self.assertEqual(graph["revision"], old_revision)
            self.assertEqual(graph["indexes"][0]["title"], "Docs")

    def test_markdown_code_block_indentation_is_not_navigation(self) -> None:
        for content in (
            "# Docs\n\n    ## Example\n",
            "# Docs\n\n\t* [Example](overview.md) - Code sample.\n",
        ):
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "indented code-block content",
                ):
                    navigation.parse_index(content, "docs/index.md")

    def test_atx_closing_markers_are_removed_and_heading_levels_preserved(self) -> None:
        parsed = navigation.parse_index(
            "# Docs #\n\n"
            "## Guides ##\n\n"
            "* [Overview](overview.md) - Start here.\n\n"
            "### Advanced ###\n\n"
            "* [More](more.md) - Go deeper.\n",
            "docs/index.md",
        )

        self.assertEqual(parsed.title, "Docs")
        self.assertEqual(
            [(section.title, section.level) for section in parsed.sections],
            [("Guides", 2), ("Advanced", 3)],
        )
        self.assertEqual(
            [link.section for link in parsed.links],
            ["Guides", "Advanced"],
        )

    def test_graph_serializes_section_title_and_level(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            commit_root(
                repository,
                "# Docs\n\n## Guides\n\n"
                "* [Overview](overview.md) - Start here.\n\n"
                "### Advanced\n\n"
                "* [Overview again](overview.md) - Go deeper.\n",
                "nested headings",
            )

            graph = navigation.collect_provider_graph("skill", repository)

            self.assertEqual(
                graph["indexes"][0]["sections"],
                [
                    {"title": "Guides", "level": 2},
                    {"title": "Advanced", "level": 3},
                ],
            )


if __name__ == "__main__":
    unittest.main()
