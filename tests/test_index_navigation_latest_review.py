import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import generate_index_navigation as navigation
from scripts.generate_index_navigation import IndexNavigationError


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def make_repository(root: Path) -> None:
    root.mkdir()
    run_git(root, "init", "-q")
    run_git(root, "config", "user.email", "tests@example.invalid")
    run_git(root, "config", "user.name", "Site Tests")


def commit_root(root: Path, text: str, message: str = "root") -> None:
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "index.md").write_text(text, encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "-q", "-m", message)


class LatestIndexNavigationReviewTests(unittest.TestCase):
    def test_atx_closing_markers_are_removed_and_heading_levels_preserved(self) -> None:
        parsed = navigation.parse_index(
            "# Docs #\n\n## Guide ##\n\n#### Details ###\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.title, "Docs")
        self.assertEqual(
            [(section.title, section.level) for section in parsed.sections],
            [("Guide", 2), ("Details", 4)],
        )

    def test_markdown_code_block_indentation_is_not_navigation(self) -> None:
        cases = (
            "# Docs\n\n    ## Hidden\n",
            "# Docs\n\n\t* [Hidden](hidden.md) - Hidden.\n",
        )
        for text in cases:
            with self.subTest(text=text), self.assertRaisesRegex(
                IndexNavigationError,
                "indented code-block content",
            ):
                navigation.parse_index(text, "docs/index.md")

    def test_directory_dot_markers_do_not_collapse_to_regular_files(self) -> None:
        entries = {
            "docs/index.md": ("blob", "100644", "a" * 40),
            "docs/overview.md": ("blob", "100644", "b" * 40),
        }
        for target in ("overview.md/.", "overview.md/%2E"):
            with self.subTest(target=target):
                link = navigation.ParsedLink(
                    label="Overview",
                    raw_target=target,
                    description="Overview.",
                    section=None,
                    line=3,
                )
                with self.assertRaisesRegex(IndexNavigationError, "slash-terminated"):
                    navigation.resolve_link("docs/index.md", link, entries)

    def test_repository_root_directory_resolves_root_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            (repository / "docs").mkdir()
            (repository / "docs" / "index.md").write_text(
                "# Docs\n\n* [Repository root](../) - Root.\n",
                encoding="utf-8",
            )
            (repository / "index.md").write_text(
                "# Repository root\n\n* [Overview](README.md) - Overview.\n",
                encoding="utf-8",
            )
            (repository / "README.md").write_text("# Overview\n", encoding="utf-8")
            run_git(repository, "add", ".")
            run_git(repository, "commit", "-q", "-m", "root index")

            graph = navigation.collect_provider_graph("skill", repository)

            self.assertIn("index.md", [item["path"] for item in graph["indexes"]])
            edge = next(
                item for item in graph["edges"] if item["label"] == "Repository root"
            )
            self.assertEqual(edge["kind"], "index")
            self.assertEqual(edge["target"], "index.md")

    def test_external_hosts_reject_whitespace_and_percent_encoding(self) -> None:
        cases = (
            # A literal source space means the bare CommonMark destination never forms;
            # fail closed at the reserved-index syntax boundary before URL parsing.
            ("https://exa mple.com/path", "unsupported index.md content"),
            ("https://exa%20mple.com/path", "malformed external link"),
        )
        for target, expected in cases:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - Invalid hostname.\n",
                    "bad host",
                )
                with self.assertRaisesRegex(IndexNavigationError, expected):
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
            run_git(repository, "commit", "-q", "-m", "non utf8")
            commit_root(repository, "# Docs\n", "root")

            graph = navigation.collect_provider_graph("skill", repository)
            self.assertEqual(graph["diagnostics"]["index_count"], 1)

    def test_tree_listing_is_pinned_to_recorded_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            commit_root(repository, "# Docs\n", "first")
            first = run_git(repository, "rev-parse", "HEAD").stdout.strip()
            (repository / "later.md").write_text("later\n", encoding="utf-8")
            run_git(repository, "add", ".")
            run_git(repository, "commit", "-q", "-m", "second")

            entries = navigation.read_entries_at_revision(repository, first)
            paths = {entry.path.decode("utf-8") for entry in entries}
            self.assertNotIn("later.md", paths)

    def test_graph_serializes_section_title_and_level(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            commit_root(repository, "# Docs\n\n### Deep section\n", "sections")

            graph = navigation.collect_provider_graph("skill", repository)
            self.assertEqual(
                graph["indexes"][0]["sections"],
                [{"title": "Deep section", "level": 3}],
            )


if __name__ == "__main__":
    unittest.main()
