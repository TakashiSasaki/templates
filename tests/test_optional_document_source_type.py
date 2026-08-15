from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import AssemblyError, assemble


class OptionalDocumentSourceTypeTests(unittest.TestCase):
    def test_existing_optional_directory_is_not_treated_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            output = base / "build"
            docs = site / "docs"
            docs.mkdir(parents=True)
            (docs / "index.md").write_text("# Portal\n", encoding="utf-8")
            (docs / "optional.md").mkdir()

            (docs / "publication-catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "documents": [
                            {
                                "id": "portal-home",
                                "source": "docs/index.md",
                                "optional": False,
                                "home": True,
                            },
                            {
                                "id": "optional-page",
                                "source": "docs/optional.md",
                                "optional": True,
                                "home": False,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
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
                                "title": "Optional",
                                "publication": "site",
                                "document": "optional-page",
                                "destination": "optional/index.md",
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

            with self.assertRaisesRegex(
                AssemblyError,
                "publication document must be a regular file",
            ):
                assemble({"site": site}, site, output)


if __name__ == "__main__":
    unittest.main()
