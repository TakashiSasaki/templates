from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import assemble


class ExplicitPublicationAssetTests(unittest.TestCase):
    @staticmethod
    def write_catalog(
        root: Path,
        *,
        document_id: str,
        source: str,
    ) -> None:
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "documents": [
                        {
                            "id": document_id,
                            "source": source,
                            "optional": False,
                            "home": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_undeclared_provider_assets_are_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            skill = base / "skill"
            output = base / "build"

            (site / "docs").mkdir(parents=True)
            (site / "docs" / "index.md").write_text(
                "# Portal\n",
                encoding="utf-8",
            )
            self.write_catalog(
                site,
                document_id="portal-home",
                source="docs/index.md",
            )
            (site / "site-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "home": {
                            "publication": "site",
                            "document": "portal-home",
                        },
                        "navigation": [
                            {
                                "title": "Home",
                                "publication": "site",
                                "document": "portal-home",
                                "destination": "index.md",
                            },
                            {
                                "title": "Skill",
                                "publication": "skill",
                                "document": "overview",
                                "destination": "skill/index.md",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (site / "zensical.template.toml").write_text(
                'site_name = "test"\nnav = __GENERATED_NAV__\n',
                encoding="utf-8",
            )

            skill.mkdir()
            (skill / "README.md").write_text("# Skill\n", encoding="utf-8")
            self.write_catalog(
                skill,
                document_id="overview",
                source="README.md",
            )
            assets = skill / "assets"
            assets.mkdir()
            (assets / "README.md").write_text(
                "# Internal asset notes\n",
                encoding="utf-8",
            )
            (assets / "icon.svg").write_text(
                "<svg></svg>\n",
                encoding="utf-8",
            )

            assemble({"site": site, "skill": skill}, site, output)

            self.assertFalse((output / "docs" / "skill" / "assets").exists())


if __name__ == "__main__":
    unittest.main()
