from __future__ import annotations

import unittest

from scripts.generate_index_navigation_viewer import provider_render_indexes


class CountingEdges(list[dict[str, object]]):
    def __init__(self, values: list[dict[str, object]]) -> None:
        super().__init__(values)
        self.yield_count = 0

    def __iter__(self):
        for value in super().__iter__():
            self.yield_count += 1
            yield value


class ProviderRenderIndexingTests(unittest.TestCase):
    def test_provider_render_indexes_scans_edges_once(self) -> None:
        child_count = 200
        indexes = [
            {
                "path": "docs/index.md",
                "title": "Docs",
                "sections": [],
                "depth": 0,
                "object_id": "a" * 40,
            },
            *[
                {
                    "path": f"docs/section-{index}/index.md",
                    "title": f"Section {index}",
                    "sections": [],
                    "depth": 1,
                    "object_id": "b" * 40,
                }
                for index in range(child_count)
            ],
        ]
        edges = CountingEdges(
            [
                {
                    "source": "docs/index.md",
                    "section": None,
                    "label": f"Section {index}",
                    "description": "Synthetic scaling edge.",
                    "line": index + 3,
                    "raw_target": f"section-{index}/",
                    "kind": "index",
                    "target": f"docs/section-{index}/index.md",
                    "fragment": None,
                }
                for index in range(child_count)
            ]
        )
        provider = {
            "name": "skill",
            "revision": "c" * 40,
            "root_index": "docs/index.md",
            "indexes": indexes,
            "edges": edges,
            "diagnostics": {},
        }

        index_by_path, parents, edges_by_source = provider_render_indexes(provider)

        self.assertEqual(edges.yield_count, child_count)
        self.assertEqual(len(index_by_path), child_count + 1)
        self.assertEqual(len(parents), child_count)
        self.assertEqual(len(edges_by_source["docs/index.md"]), child_count)
        self.assertTrue(
            all(
                not edges_by_source[f"docs/section-{index}/index.md"]
                for index in range(child_count)
            )
        )


if __name__ == "__main__":
    unittest.main()
