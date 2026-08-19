from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.publication_link_rewriter import rebase_publication_links


class PublicationLinkRewriterTests(unittest.TestCase):
    def write_catalog(self, root: Path) -> None:
        catalog = {
            "schema_version": 3,
            "documents": [
                {
                    "id": "overview",
                    "source": "docs/index.md",
                    "optional": False,
                    "home": True,
                },
                {
                    "id": "runtime",
                    "source": "components/capability.runtime/files/RUNTIME.md",
                    "optional": False,
                    "home": False,
                },
                {
                    "id": "skill-docs",
                    "source": "components/artifact.skill-core/files/docs/index.md",
                    "optional": False,
                    "home": False,
                },
            ],
            "assets": [
                {
                    "source": "catalog/catalog.json",
                    "destination": "machine/catalog.json",
                    "optional": False,
                }
            ],
        }
        path = root / "docs/publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalog), encoding="utf-8")

    def write_manifest(self, root: Path) -> None:
        manifest = {
            "schema_version": 2,
            "home": {"publication": "composition", "document": "overview"},
            "navigation": [
                {
                    "title": "Overview",
                    "publication": "composition",
                    "document": "overview",
                    "destination": "composition/docs/index.md",
                },
                {
                    "title": "Runtime",
                    "publication": "composition",
                    "document": "runtime",
                    "destination": "capabilities/runtime/index.md",
                },
                {
                    "title": "Skill docs",
                    "publication": "composition",
                    "document": "skill-docs",
                    "destination": "skill/docs/index.md",
                },
            ],
        }
        root.mkdir(parents=True, exist_ok=True)
        (root / "site-manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    def test_rebases_cataloged_documents_and_assets_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            provider = base / "composition"
            site = base / "site"
            output = base / "build"

            self.write_catalog(provider)
            self.write_manifest(site)
            runtime = provider / "components/capability.runtime/files/RUNTIME.md"
            runtime.parent.mkdir(parents=True, exist_ok=True)
            runtime.write_text("# Runtime\n", encoding="utf-8")
            skill_docs = provider / "components/artifact.skill-core/files/docs/index.md"
            skill_docs.parent.mkdir(parents=True, exist_ok=True)
            skill_docs.write_text("# Skill docs\n", encoding="utf-8")
            catalog_asset = provider / "catalog/catalog.json"
            catalog_asset.parent.mkdir(parents=True, exist_ok=True)
            catalog_asset.write_text("{}\n", encoding="utf-8")

            source_text = """# Overview

[Runtime](../components/capability.runtime/files/RUNTIME.md?mode=1#decision)
[Runtime angle](<../components/capability.runtime/files/RUNTIME.md#angle>)
[Skill docs](../components/artifact.skill-core/files/docs/)
[Catalog](../catalog/catalog.json)
[External](https://example.com/docs.md)
[Mail](mailto:docs@example.com)
[Root](/docs/absolute.md)
[Anchor](#local)
[Unknown](../not-published.md)
[Escape](../../../../etc/passwd)
`[Inline code](../components/capability.runtime/files/RUNTIME.md)`

[run]: ../components/capability.runtime/files/RUNTIME.md#reference

```markdown
[Fenced code](../components/capability.runtime/files/RUNTIME.md)
```
"""
            source = provider / "docs/index.md"
            source.write_text(source_text, encoding="utf-8")

            overview_output = output / "docs/composition/docs/index.md"
            overview_output.parent.mkdir(parents=True, exist_ok=True)
            overview_output.write_text(source_text, encoding="utf-8")
            runtime_output = output / "docs/capabilities/runtime/index.md"
            runtime_output.parent.mkdir(parents=True, exist_ok=True)
            runtime_output.write_text("# Runtime\n", encoding="utf-8")
            skill_docs_output = output / "docs/skill/docs/index.md"
            skill_docs_output.parent.mkdir(parents=True, exist_ok=True)
            skill_docs_output.write_text("# Skill docs\n", encoding="utf-8")
            asset_output = output / "docs/composition/machine/catalog.json"
            asset_output.parent.mkdir(parents=True, exist_ok=True)
            asset_output.write_text("{}\n", encoding="utf-8")

            count = rebase_publication_links(
                {"composition": provider},
                site,
                output,
            )

            self.assertEqual(count, 5)
            published = overview_output.read_text(encoding="utf-8")
            self.assertIn(
                "[Runtime](../../capabilities/runtime/index.md?mode=1#decision)",
                published,
            )
            self.assertIn(
                "[Runtime angle](<../../capabilities/runtime/index.md#angle>)",
                published,
            )
            self.assertIn("[Skill docs](../../skill/docs/index.md)", published)
            self.assertIn("[Catalog](../machine/catalog.json)", published)
            self.assertIn(
                "[run]: ../../capabilities/runtime/index.md#reference",
                published,
            )
            for unchanged in (
                "[External](https://example.com/docs.md)",
                "[Mail](mailto:docs@example.com)",
                "[Root](/docs/absolute.md)",
                "[Anchor](#local)",
                "[Unknown](../not-published.md)",
                "[Escape](../../../../etc/passwd)",
                "`[Inline code](../components/capability.runtime/files/RUNTIME.md)`",
                "[Fenced code](../components/capability.runtime/files/RUNTIME.md)",
            ):
                self.assertIn(unchanged, published)

    def test_missing_optional_output_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            provider = base / "composition"
            site = base / "site"
            output = base / "build"

            catalog = {
                "schema_version": 3,
                "documents": [
                    {
                        "id": "overview",
                        "source": "README.md",
                        "optional": False,
                        "home": True,
                    },
                    {
                        "id": "optional",
                        "source": "docs/optional.md",
                        "optional": True,
                        "home": False,
                    },
                ],
            }
            catalog_path = provider / "docs/publication-catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            (provider / "README.md").write_text(
                "[Optional](docs/optional.md)\n",
                encoding="utf-8",
            )

            manifest = {
                "schema_version": 2,
                "home": {"publication": "composition", "document": "overview"},
                "navigation": [
                    {
                        "title": "Overview",
                        "publication": "composition",
                        "document": "overview",
                        "destination": "composition/index.md",
                    },
                    {
                        "title": "Optional",
                        "publication": "composition",
                        "document": "optional",
                        "destination": "composition/optional.md",
                    },
                ],
            }
            site.mkdir(parents=True)
            (site / "site-manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            target = output / "docs/composition/index.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("[Optional](docs/optional.md)\n", encoding="utf-8")

            count = rebase_publication_links(
                {"composition": provider},
                site,
                output,
            )

            self.assertEqual(count, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "[Optional](docs/optional.md)\n",
            )


if __name__ == "__main__":
    unittest.main()
