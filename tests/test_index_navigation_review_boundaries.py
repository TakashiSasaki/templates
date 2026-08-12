from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import (
    IndexNavigationError,
    MAX_INDEX_BYTES,
    ParsedLink,
    collect_provider_graph,
    find_cycle_edges,
    parse_index,
    resolve_link,
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


def make_repository(root: Path) -> None:
    root.mkdir()
    run_git(root, "init", "--quiet")
    run_git(root, "config", "user.email", "tests@example.invalid")
    run_git(root, "config", "user.name", "Index navigation review tests")
    (root / "docs").mkdir()
    (root / "docs/index.md").write_text(
        "# Docs\n\n* [Overview](overview.md) - Read the overview.\n",
        encoding="utf-8",
    )
    (root / "docs/overview.md").write_text("# Overview\n", encoding="utf-8")
    run_git(root, "add", ".")
    run_git(root, "commit", "--quiet", "--message", "fixture")


def commit_root(repository: Path, text: str, message: str) -> None:
    (repository / "docs/index.md").write_text(text, encoding="utf-8")
    run_git(repository, "add", "docs/index.md")
    run_git(repository, "commit", "--quiet", "--message", message)


class IndexNavigationReviewBoundaryTests(unittest.TestCase):
    def test_percent_decoded_fragment_controls_fail_closed(self) -> None:
        for fragment in ("%0A", "%E2%80%AE"):
            with self.subTest(fragment=fragment), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad](#{fragment}) - Invalid fragment.\n",
                    "invalid fragment",
                )
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "fragment contains a disallowed control character",
                ):
                    collect_provider_graph("skill", repository)

    def test_percent_decoded_path_controls_fail_closed(self) -> None:
        for target in ("overview%07.md", "overview%E2%80%AE.md"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - Invalid decoded path.\n",
                    "invalid decoded path",
                )
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "link path contains a disallowed control character",
                ):
                    collect_provider_graph("skill", repository)

    def test_external_urls_reject_invalid_ports(self) -> None:
        for target in (
            "https://example.com:bad/path",
            "https://example.com:70000/path",
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - Invalid external port.\n",
                    "invalid external port",
                )
                with self.assertRaisesRegex(IndexNavigationError, "malformed external link"):
                    collect_provider_graph("skill", repository)

    def test_regular_file_targets_reject_trailing_slashes(self) -> None:
        for target in ("overview.md/", "overview.md%2F"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                make_repository(repository)
                commit_root(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - File path must not end with slash.\n",
                    "trailing slash",
                )
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "slash-terminated repository link targets a regular file",
                ):
                    collect_provider_graph("skill", repository)

    def test_root_level_index_md_is_classified_as_index(self) -> None:
        link = ParsedLink(
            label="Repository index",
            raw_target="../index.md",
            description="Follow a root-level index.",
            section=None,
            line=3,
        )
        entries = {"index.md": ("blob", "100644", "a" * 40)}

        resolved = resolve_link("docs/index.md", link, entries)

        self.assertEqual(resolved["kind"], "index")
        self.assertEqual(resolved["target"], "index.md")

    def test_unreachable_oversized_index_does_not_block_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            archive = repository / "archive"
            archive.mkdir()
            (archive / "index.md").write_text(
                "# Archive\n" + ("x" * (MAX_INDEX_BYTES + 1)),
                encoding="utf-8",
            )
            run_git(repository, "add", "archive/index.md")
            run_git(repository, "commit", "--quiet", "--message", "unreachable oversized index")

            graph = collect_provider_graph("skill", repository)
            self.assertEqual(
                [index["path"] for index in graph["indexes"]],
                ["docs/index.md"],
            )

    def test_reachable_oversized_index_still_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            make_repository(repository)
            child = repository / "docs/child"
            child.mkdir()
            (child / "index.md").write_text(
                "# Child\n" + ("x" * (MAX_INDEX_BYTES + 1)),
                encoding="utf-8",
            )
            commit_root(
                repository,
                "# Docs\n\n* [Child](child/) - Follow the child index.\n",
                "link oversized child",
            )
            run_git(repository, "add", "docs/child/index.md")
            run_git(repository, "commit", "--quiet", "--message", "oversized child")

            with self.assertRaisesRegex(IndexNavigationError, "index exceeds 256 KiB limit"):
                collect_provider_graph("skill", repository)

    def test_cycle_scan_is_iterative_for_deep_graphs(self) -> None:
        adjacency = {
            f"docs/node-{index}/index.md": [f"docs/node-{index + 1}/index.md"]
            for index in range(1100)
        }
        root = "docs/node-0/index.md"
        adjacency["docs/node-1100/index.md"] = [root]

        self.assertEqual(
            find_cycle_edges(adjacency, root),
            [{"source": "docs/node-1100/index.md", "target": root}],
        )

    def test_non_regular_file_and_gitlink_targets_fail_closed(self) -> None:
        link = ParsedLink(
            label="Target",
            raw_target="target.md",
            description="Invalid target mode.",
            section=None,
            line=3,
        )
        for mode in ("120000", "160000"):
            with self.subTest(mode=mode):
                kind = "commit" if mode == "160000" else "blob"
                entries = {"docs/target.md": (kind, mode, "a" * 40)}
                with self.assertRaisesRegex(
                    IndexNavigationError,
                    "not a regular file or directory",
                ):
                    resolve_link("docs/index.md", link, entries)

    def test_en_dash_link_separator_is_accepted(self) -> None:
        parsed = parse_index(
            "# Docs\n\n* [Overview](overview.md) – Read the overview.\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.links[0].raw_target, "overview.md")


if __name__ == "__main__":
    unittest.main()
