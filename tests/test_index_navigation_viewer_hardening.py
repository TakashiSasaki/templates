from __future__ import annotations

import copy
import unittest

from scripts.generate_index_navigation_viewer import (
    IndexNavigationViewerError,
    index_page_path,
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


def edge(
    target: str,
    *,
    kind: str = "external",
    fragment: str | None = None,
) -> dict[str, object]:
    return {
        "source": "docs/index.md",
        "section": None,
        "label": "Target",
        "description": "Boundary test target.",
        "line": 3,
        "raw_target": target,
        "kind": kind,
        "target": target,
        "fragment": fragment,
    }


class IndexNavigationViewerHardeningTests(unittest.TestCase):
    def test_repository_paths_reject_reserved_and_noncanonical_forms(self) -> None:
        for path in (
            "docs/.git/index.md",
            "docs/.GIT/index.md",
            "/docs/index.md",
            "docs\\index.md",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    IndexNavigationViewerError,
                    "safe repository-relative path",
                ):
                    validate_repository_path(path, "test path")

    def test_repository_paths_allow_producer_valid_colons(self) -> None:
        validate_repository_path("docs/file:stream/index.md", "test path")

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

    def test_fragment_controls_are_rejected_in_tampered_graphs(self) -> None:
        for fragment in ("bad\nfragment", "bad\u202efragment"):
            with self.subTest(fragment=fragment):
                graph = provider_graph()
                record = edge("docs/index.md", kind="fragment", fragment=fragment)
                record["raw_target"] = f"#{fragment}"
                graph["edges"] = [record]
                with self.assertRaisesRegex(
                    IndexNavigationViewerError,
                    "edge fragment is invalid",
                ):
                    validate_provider_graph(graph)

    def test_external_edges_reject_other_schemes_missing_hosts_and_invalid_ports(self) -> None:
        base = provider_graph()
        for target in (
            "file:///etc/passwd",
            "ftp://example.com/spec",
            "https:///local",
            "https://example.com:bad/spec",
            "https://example.com:70000/spec",
        ):
            with self.subTest(target=target):
                graph = copy.deepcopy(base)
                graph["edges"] = [edge(target)]
                with self.assertRaisesRegex(
                    IndexNavigationViewerError,
                    "external edge target is invalid",
                ):
                    validate_provider_graph(graph)

    def test_tampered_graph_rejects_noncanonical_shas_and_unsafe_internal_paths(self) -> None:
        base = provider_graph()

        tampered = copy.deepcopy(base)
        tampered["revision"] = "A" * 40
        with self.assertRaisesRegex(IndexNavigationViewerError, "revision is invalid"):
            validate_provider_graph(tampered)

        tampered = copy.deepcopy(base)
        tampered["indexes"][0]["object_id"] = "g" * 40
        with self.assertRaisesRegex(IndexNavigationViewerError, "index record is invalid"):
            validate_provider_graph(tampered)

        tampered = copy.deepcopy(base)
        tampered["indexes"][1]["path"] = "docs/../escape/index.md"
        with self.assertRaisesRegex(
            IndexNavigationViewerError,
            "safe repository-relative path",
        ):
            validate_provider_graph(tampered)

        tampered = copy.deepcopy(base)
        tampered["edges"] = [edge("../../escape.md", kind="file")]
        with self.assertRaisesRegex(
            IndexNavigationViewerError,
            "safe repository-relative path",
        ):
            validate_provider_graph(tampered)

        with self.assertRaisesRegex(
            IndexNavigationViewerError,
            "safe repository-relative path",
        ):
            index_page_path("skill", "docs/../../escape/index.md")


if __name__ == "__main__":
    unittest.main()
