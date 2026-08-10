from __future__ import annotations

import copy
import unittest

from scripts.generate_index_navigation_viewer import (
    IndexNavigationViewerError,
    validate_provider_graph,
    validate_repository_path,
)


def provider_graph() -> dict[str, object]:
    return {
        "name": "skill",
        "revision": "a" * 40,
        "root_index": "docs/index.md",
        "indexes": [
            {
                "path": "docs/index.md",
                "title": "Docs",
                "sections": [],
                "depth": 0,
                "object_id": "b" * 40,
            },
            {
                "path": "docs/architecture/index.md",
                "title": "Architecture",
                "sections": [],
                "depth": 1,
                "object_id": "c" * 40,
            },
        ],
        "edges": [],
        "diagnostics": {},
    }


class IndexNavigationViewerHardeningTests(unittest.TestCase):
    def test_repository_paths_reject_git_components_and_colons(self) -> None:
        for path in (
            "docs/.git/index.md",
            "docs/.GIT/index.md",
            "docs/file:stream/index.md",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    IndexNavigationViewerError,
                    "safe repository-relative path",
                ):
                    validate_repository_path(path, "test path")

    def test_fragment_edge_must_target_its_source_index(self) -> None:
        graph = provider_graph()
        graph["edges"] = [
            {
                "source": "docs/index.md",
                "section": None,
                "label": "Details",
                "description": "Invalid cross-index fragment.",
                "line": 3,
                "raw_target": "architecture/#details",
                "kind": "fragment",
                "target": "docs/architecture/index.md",
                "fragment": "details",
            }
        ]

        with self.assertRaisesRegex(
            IndexNavigationViewerError,
            "fragment edge must target its source index",
        ):
            validate_provider_graph(graph)

    def test_external_edges_reject_other_schemes_and_missing_hosts(self) -> None:
        base = provider_graph()
        for target in (
            "file:///etc/passwd",
            "ftp://example.com/spec",
            "https:///local",
        ):
            with self.subTest(target=target):
                graph = copy.deepcopy(base)
                graph["edges"] = [
                    {
                        "source": "docs/index.md",
                        "section": None,
                        "label": "External",
                        "description": "Invalid external target.",
                        "line": 3,
                        "raw_target": target,
                        "kind": "external",
                        "target": target,
                        "fragment": None,
                    }
                ]
                with self.assertRaisesRegex(
                    IndexNavigationViewerError,
                    "external edge target is invalid",
                ):
                    validate_provider_graph(graph)


if __name__ == "__main__":
    unittest.main()
