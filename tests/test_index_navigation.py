from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import (
    IndexNavigationError,
    PROVIDER_ORDER,
    collect_provider_graph,
    generate_graph,
    parse_index,
    parse_providers,
    write_graph,
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


class IndexNavigationTests(unittest.TestCase):
    def make_repository(self, root: Path, *, cycle: bool = False) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Index navigation tests")
        (root / "docs/architecture").mkdir(parents=True)
        (root / "template/docs").mkdir(parents=True)
        (root / "docs/index.md").write_text(
            "# Provider documentation\n\n"
            "## Start here\n\n"
            "* [Architecture](architecture/) - Follow the architecture index.\n"
            "* [Consumer docs](../template/docs/) - Follow the copyable documentation index.\n"
            "* [Overview](overview.md#scope) - Read the provider overview.\n"
            "* [Specification](https://example.com/spec) - Read the external specification.\n",
            encoding="utf-8",
        )
        architecture_tail = (
            "* [Back to root](../) - Exercise a cycle without making traversal recursive forever.\n"
            if cycle
            else ""
        )
        (root / "docs/architecture/index.md").write_text(
            "# Architecture\n\n"
            "## Design\n\n"
            "* [Boundary](boundary.md) - Defines the distribution boundary.\n"
            + architecture_tail,
            encoding="utf-8",
        )
        (root / "template/docs/index.md").write_text(
            "# Consumer documentation\n\n"
            "## Contracts\n\n"
            "* [Runtime](../RUNTIME.md) - Defines runtime selection.\n",
            encoding="utf-8",
        )
        (root / "docs/overview.md").write_text("# Overview\n", encoding="utf-8")
        (root / "docs/architecture/boundary.md").write_text(
            "# Boundary\n", encoding="utf-8"
        )
        (root / "template/RUNTIME.md").write_text("# Runtime\n", encoding="utf-8")
        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def commit_root_index(self, repository: Path, text: str, message: str) -> None:
        (repository / "docs/index.md").write_text(text, encoding="utf-8")
        run_git(repository, "add", "docs/index.md")
        run_git(repository, "commit", "--quiet", "--message", message)

    def test_collects_recursive_indexes_and_classifies_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            graph = collect_provider_graph("skill", repository)

            self.assertEqual(graph["root_index"], "docs/index.md")
            self.assertEqual(len(graph["revision"]), 40)
            self.assertEqual(
                [item["path"] for item in graph["indexes"]],
                [
                    "docs/index.md",
                    "docs/architecture/index.md",
                    "template/docs/index.md",
                ],
            )
            kinds = {(edge["label"], edge["kind"]) for edge in graph["edges"]}
            self.assertIn(("Architecture", "index"), kinds)
            self.assertIn(("Consumer docs", "index"), kinds)
            self.assertIn(("Overview", "file"), kinds)
            self.assertIn(("Specification", "external"), kinds)
            overview = next(edge for edge in graph["edges"] if edge["label"] == "Overview")
            self.assertEqual(overview["target"], "docs/overview.md")
            self.assertEqual(overview["fragment"], "scope")
            self.assertEqual(graph["diagnostics"]["max_index_depth"], 1)

    def test_reads_committed_blob_instead_of_mutable_working_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            (repository / "docs/index.md").write_text(
                "# Uncommitted replacement\n", encoding="utf-8"
            )
            graph = collect_provider_graph("skill", repository)
            root_index = next(
                value for value in graph["indexes"] if value["path"] == "docs/index.md"
            )
            self.assertEqual(root_index["title"], "Provider documentation")

    def test_executable_git_blobs_are_regular_navigation_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            run_git(repository, "update-index", "--chmod=+x", "docs/index.md")
            run_git(repository, "update-index", "--chmod=+x", "docs/overview.md")
            run_git(repository, "commit", "--quiet", "--message", "executable regular files")

            graph = collect_provider_graph("skill", repository)
            root = next(index for index in graph["indexes"] if index["path"] == "docs/index.md")
            overview = next(edge for edge in graph["edges"] if edge["label"] == "Overview")
            self.assertEqual(root["title"], "Provider documentation")
            self.assertEqual(overview["kind"], "file")
            self.assertEqual(overview["target"], "docs/overview.md")

    def test_cycle_is_reported_without_rejecting_valid_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository, cycle=True)
            graph = collect_provider_graph("skill", repository)
            self.assertEqual(
                graph["diagnostics"]["cycle_edges"],
                [{"source": "docs/architecture/index.md", "target": "docs/index.md"}],
            )

    def test_duplicate_cycle_links_produce_one_diagnostic_edge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            (repository / "docs/architecture/index.md").write_text(
                "# Architecture\n\n"
                "## Design\n\n"
                "* [Back to root](../) - First cyclic route.\n"
                "* [Back to root again](../) - Duplicate cyclic route.\n",
                encoding="utf-8",
            )
            run_git(repository, "add", "docs/architecture/index.md")
            run_git(repository, "commit", "--quiet", "--message", "duplicate cycle route")
            graph = collect_provider_graph("skill", repository)
            self.assertEqual(
                graph["diagnostics"]["cycle_edges"],
                [{"source": "docs/architecture/index.md", "target": "docs/index.md"}],
            )

    def test_multiple_parent_diagnostic_counts_distinct_source_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            self.commit_root_index(
                repository,
                "# Provider documentation\n\n"
                "## First route\n\n"
                "* [Architecture](architecture/) - First link from the root.\n\n"
                "## Second route\n\n"
                "* [Architecture again](architecture/) - Second link from the same root.\n",
                "duplicate edge from same parent",
            )
            graph = collect_provider_graph("skill", repository)
            self.assertEqual(graph["diagnostics"]["multiple_parent_indexes"], [])

    def test_repository_escape_and_broken_links_fail_closed(self) -> None:
        parsed = parse_index(
            "# Docs\n\n* [Escape](../../outside.md) - Must fail.\n",
            "docs/index.md",
        )
        self.assertEqual(parsed.links[0].raw_target, "../../outside.md")

        for target, message in (
            ("../../outside.md", "escapes repository root"),
            ("missing.md", "broken repository link"),
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary) / "provider"
                self.make_repository(repository)
                self.commit_root_index(
                    repository,
                    f"# Docs\n\n* [Bad]({target}) - Invalid target.\n",
                    "bad link",
                )
                with self.assertRaisesRegex(IndexNavigationError, message):
                    collect_provider_graph("skill", repository)

    def test_index_shape_rejects_prose_duplicate_sections_and_unsafe_external_scheme(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported index.md content"):
            parse_index("# Docs\n\nFree-form prose.\n", "docs/index.md")
        with self.assertRaisesRegex(IndexNavigationError, "duplicate section heading"):
            parse_index(
                "# Docs\n\n## Examples\n\n* [One](one.md) - First.\n\n"
                "## Examples\n\n* [Two](two.md) - Second.\n",
                "docs/index.md",
            )

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            self.commit_root_index(
                repository,
                "# Docs\n\n* [Unsafe](javascript:alert) - Must fail.\n",
                "unsafe scheme",
            )
            with self.assertRaisesRegex(IndexNavigationError, "unsupported external link"):
                collect_provider_graph("skill", repository)

    def test_link_target_may_contain_balanced_parentheses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            self.commit_root_index(
                repository,
                "# Docs\n\n"
                "* [Spec](https://example.com/spec_(v1)) - Parentheses are valid target text.\n",
                "parenthesized URL",
            )
            graph = collect_provider_graph("skill", repository)
            edge = graph["edges"][0]
            self.assertEqual(edge["kind"], "external")
            self.assertEqual(edge["target"], "https://example.com/spec_(v1)")

    def test_external_queries_fail_and_fragments_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            self.commit_root_index(
                repository,
                "# Docs\n\n"
                "* [Spec](https://example.com/spec#caf%C3%A9) - Encoded fragment.\n",
                "encoded external fragment",
            )
            graph = collect_provider_graph("skill", repository)
            edge = graph["edges"][0]
            self.assertEqual(edge["target"], "https://example.com/spec")
            self.assertEqual(edge["fragment"], "café")

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            self.commit_root_index(
                repository,
                "# Docs\n\n"
                "* [Search](https://example.com/spec?q=test) - Queries are not accepted.\n",
                "external query",
            )
            with self.assertRaisesRegex(IndexNavigationError, "must not contain a query"):
                collect_provider_graph("skill", repository)

    def test_repository_queries_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "provider"
            self.make_repository(repository)
            self.commit_root_index(
                repository,
                "# Docs\n\n"
                "* [Overview](overview.md?view=compact) - Queries are not accepted.\n",
                "repository query",
            )
            with self.assertRaisesRegex(IndexNavigationError, "must not contain a query"):
                collect_provider_graph("skill", repository)

    def test_generate_graph_requires_exact_provider_order_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repositories = {}
            for provider in PROVIDER_ORDER:
                repository = root / provider
                self.make_repository(repository)
                repositories[provider] = repository

            graph = generate_graph("TakashiSasaki/templates", repositories)
            self.assertEqual(graph["schema_version"], 1)
            self.assertEqual(
                [provider["name"] for provider in graph["providers"]],
                list(PROVIDER_ORDER),
            )
            output = root / "generated/index-navigation.json"
            write_graph(output, graph)
            loaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(loaded, graph)

            with self.assertRaisesRegex(IndexNavigationError, "providers must be supplied"):
                generate_graph(
                    "TakashiSasaki/templates",
                    {
                        "policy": repositories["policy"],
                        "skill": repositories["skill"],
                        "webapp": repositories["webapp"],
                    },
                )

    def test_cli_provider_parser_rejects_duplicates_and_wrong_order(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "duplicate provider"):
            parse_providers(
                ["skill=a", "skill=b", "policy=c", "webapp=d"]
            )
        with self.assertRaisesRegex(IndexNavigationError, "providers must be supplied"):
            parse_providers(["policy=a", "skill=b", "webapp=c"])


if __name__ == "__main__":
    unittest.main()
