import unittest
from unittest.mock import patch

from scripts import generate_index_navigation_viewer as viewer
from scripts.generate_index_navigation_viewer import IndexNavigationViewerError


def minimal_provider() -> dict[str, object]:
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
            }
        ],
        "edges": [],
        "diagnostics": {
            "index_count": 1,
            "edge_count": 0,
            "max_index_depth": 0,
            "cycle_edges": [],
            "multiple_parent_indexes": [],
        },
    }


class LatestIndexNavigationViewerReviewRoundGTests(unittest.TestCase):
    def test_diagnostic_counts_require_exact_integers(self) -> None:
        provider = minimal_provider()
        provider["diagnostics"] = {
            "index_count": True,
            "edge_count": False,
            "max_index_depth": False,
            "cycle_edges": [],
            "multiple_parent_indexes": [],
        }
        with self.assertRaisesRegex(IndexNavigationViewerError, "diagnostics"):
            viewer.validate_provider_graph(provider)

    def test_heading_anchor_suffix_allocation_is_linear(self) -> None:
        values = [
            "A" + format(index, "010b").translate(str.maketrans("01", ".!")) + "B"
            for index in range(1024)
        ]
        original = viewer.IDCOUNT_RE
        calls = 0

        class CountingRegex:
            def match(self, value: str):
                nonlocal calls
                calls += 1
                return original.match(value)

        with patch.object(viewer, "IDCOUNT_RE", CountingRegex()):
            anchors = viewer.heading_anchors(values)

        self.assertEqual(anchors[0], "ab")
        self.assertEqual(anchors[-1], "ab_1023")
        self.assertLessEqual(calls, len(values) * 2)

    def test_lone_surrogate_fragment_is_rejected_before_rendering(self) -> None:
        provider = minimal_provider()
        provider["edges"] = [
            {
                "source": "docs/index.md",
                "section": None,
                "label": "Top",
                "description": "Return to top.",
                "line": 1,
                "raw_target": "#top",
                "kind": "fragment",
                "target": "docs/index.md",
                "fragment": chr(0xD800),
            }
        ]
        provider["diagnostics"]["edge_count"] = 1
        with self.assertRaisesRegex(IndexNavigationViewerError, "fragment is invalid"):
            viewer.validate_provider_graph(provider)


if __name__ == "__main__":
    unittest.main()
