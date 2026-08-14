from __future__ import annotations

import unittest

from scripts.generate_index_navigation_viewer import render_index_page


REPOSITORY = "TakashiSasaki/templates"
REVISION = "a" * 40
OBJECT_ID = "b" * 40


class PolicyNavigationViewerLayerTests(unittest.TestCase):
    def test_root_renders_policy_layer_indexes_with_immutable_provenance(self) -> None:
        root_index = {
            "path": "docs/index.md",
            "title": "agent-policy navigation",
            "sections": [
                {"title": "Provider and toolchain", "level": 2},
                {"title": "Shared policy corpus", "level": 2},
                {"title": "Consumer application", "level": 2},
            ],
            "depth": 0,
            "object_id": OBJECT_ID,
        }
        layer_specs = [
            (
                "Provider and toolchain",
                "Provider and toolchain documentation",
                "docs/provider/index.md",
                5,
            ),
            (
                "Shared policy corpus",
                "Shared policy corpus",
                "docs/shared-policy/index.md",
                9,
            ),
            (
                "Consumer application",
                "Applying policy to a consumer repository",
                "docs/consumer/index.md",
                13,
            ),
        ]
        indexes = [root_index]
        edges = []
        for section, label, target, line in layer_specs:
            indexes.append(
                {
                    "path": target,
                    "title": label,
                    "sections": [],
                    "depth": 1,
                    "object_id": OBJECT_ID,
                }
            )
            edges.append(
                {
                    "source": "docs/index.md",
                    "section": section,
                    "label": label,
                    "description": "Enter this policy navigation layer.",
                    "line": line,
                    "raw_target": target.removeprefix("docs/"),
                    "kind": "index",
                    "target": target,
                    "fragment": None,
                }
            )

        provider = {
            "name": "policy",
            "revision": REVISION,
            "root_index": "docs/index.md",
            "indexes": indexes,
            "edges": edges,
            "diagnostics": {
                "index_count": len(indexes),
                "edge_count": len(edges),
                "max_index_depth": 1,
            },
        }

        page = render_index_page(REPOSITORY, provider, root_index, {})

        for _section, label, target, line in layer_specs:
            relative_directory = target.removeprefix("docs/").removesuffix("/index.md")
            self.assertIn(
                f'href="/guided/policy/docs/{relative_directory}/"',
                page,
            )
            self.assertIn(f"<strong>{label}</strong>", page)
            self.assertIn(
                f'href="https://github.com/{REPOSITORY}/blob/{REVISION}/docs/index.md#L{line}"',
                page,
            )
            self.assertIn(
                f'href="https://github.com/{REPOSITORY}/blob/{REVISION}/{target}"',
                page,
            )

        self.assertEqual(page.count('<span class="badge">index</span>'), 3)


if __name__ == "__main__":
    unittest.main()
