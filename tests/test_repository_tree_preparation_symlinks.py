from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_repository_tree_publication import PreparationError, prepare


class RepositoryTreePreparationSymlinkTests(unittest.TestCase):
    def test_preparation_rejects_symlinked_site_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_root = root / "site"
            site_root.mkdir()
            (site_root / "docs/repository-trees").mkdir(parents=True)
            (site_root / "docs/index.md").write_text("# Portal\n", encoding="utf-8")
            (site_root / "docs/publication-catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "documents": [
                            {
                                "id": "portal-home",
                                "source": "docs/index.md",
                                "optional": False,
                                "home": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (site_root / "zensical.template.toml").write_text(
                "nav = __GENERATED_NAV__\n",
                encoding="utf-8",
            )
            (site_root / "docs/repository-trees/index.md").write_text(
                "# Repository trees\n\n<!-- GENERATED_REPOSITORY_TREE_INDEX -->\n",
                encoding="utf-8",
            )
            for publication in ("skill", "policy", "webapp"):
                (site_root / f"docs/repository-trees/{publication}.md").write_text(
                    f"# {publication}\n\n"
                    f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->\n",
                    encoding="utf-8",
                )

            external_manifest = root / "external-site-manifest.json"
            external_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "home": {
                            "publication": "site",
                            "document": "portal-home",
                        },
                        "navigation": [
                            {
                                "title": "Documentation portal",
                                "publication": "site",
                                "document": "portal-home",
                                "destination": "index.md",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            os.symlink(external_manifest, site_root / "site-manifest.json")

            with self.assertRaisesRegex(
                PreparationError,
                "site manifest must be a regular file",
            ):
                prepare(site_root, root / "prepared")


if __name__ == "__main__":
    unittest.main()
