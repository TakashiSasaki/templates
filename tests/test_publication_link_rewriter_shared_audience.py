from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.publication_link_rewriter import rebase_publication_links


class SharedAudiencePublicationLinkRewriterTests(unittest.TestCase):
    def test_shared_document_is_rewritten_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            provider = base / "composition"
            site = base / "site"
            output = base / "build"

            catalog = {
                "schema_version": 3,
                "documents": [
                    {"id": "source", "source": "a/source.md", "optional": False, "home": True},
                    {"id": "target", "source": "a/target.md", "optional": False, "home": False},
                    {"id": "collision", "source": "a/y/target.md", "optional": False, "home": False},
                ],
                "assets": [],
            }
            catalog_path = provider / "docs/publication-catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            for relative in ("a/source.md", "a/target.md", "a/y/target.md"):
                path = provider / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Provider document\n", encoding="utf-8")

            manifest = {
                "schema_version": 3,
                "audiences": ["use", "maintain"],
                "home": {"publication": "composition", "document": "source"},
                "documents": [
                    {
                        "publication": "composition",
                        "document": "source",
                        "title": "Source",
                        "destination": "index.md",
                        "primary_audience": "use",
                        "additional_audiences": ["maintain"],
                    },
                    {
                        "publication": "composition",
                        "document": "target",
                        "title": "Target",
                        "destination": "y/target.md",
                        "primary_audience": "use",
                        "additional_audiences": [],
                    },
                    {
                        "publication": "composition",
                        "document": "collision",
                        "title": "Collision",
                        "destination": "wrong/target.md",
                        "primary_audience": "use",
                        "additional_audiences": [],
                    },
                ],
                "navigation": {
                    "use": [
                        {"title": "Source", "publication": "composition", "document": "source", "destination": "index.md"},
                        {"title": "Target", "publication": "composition", "document": "target", "destination": "y/target.md"},
                        {"title": "Collision", "publication": "composition", "document": "collision", "destination": "wrong/target.md"},
                    ],
                    "maintain": [
                        {"title": "Source", "publication": "composition", "document": "source", "destination": "index.md"},
                    ],
                },
            }
            site.mkdir(parents=True, exist_ok=True)
            (site / "site-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            docs = output / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            (docs / "index.md").write_text("[Target](target.md)\n", encoding="utf-8")
            for relative in ("y/target.md", "wrong/target.md"):
                path = docs / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Output\n", encoding="utf-8")

            count = rebase_publication_links({"composition": provider}, site, output)

            self.assertEqual(count, 1)
            self.assertEqual((docs / "index.md").read_text(encoding="utf-8"), "[Target](y/target.md)\n")


if __name__ == "__main__":
    unittest.main()
