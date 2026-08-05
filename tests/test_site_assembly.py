from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import AssemblyError, assemble


class MultiPublicationAssemblyTests(unittest.TestCase):
    def write_catalog(
        self,
        root: Path,
        documents: list[dict[str, object]],
        assets: list[dict[str, object]] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "schema_version": 2 if assets is not None else 1,
            "documents": documents,
        }
        if assets is not None:
            payload["assets"] = assets
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def write_site(
        self,
        root: Path,
        manifest: dict[str, object],
    ) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "site-manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (root / "zensical.template.toml").write_text(
            "site_name = \"test\"\nnav = __GENERATED_NAV__\n",
            encoding="utf-8",
        )

    def test_multiple_publications_are_namespaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            skill = base / "skill"
            policy = base / "policy"
            output = base / "build"

            (site / "docs").mkdir(parents=True)
            (site / "docs" / "index.md").write_text("# Portal\n", encoding="utf-8")
            (site / "assets").mkdir()
            (site / "assets" / "portal.txt").write_text("portal", encoding="utf-8")
            self.write_catalog(
                site,
                [
                    {
                        "id": "portal-home",
                        "source": "docs/index.md",
                        "optional": False,
                        "home": True,
                    }
                ],
            )

            skill.mkdir()
            (skill / "README.md").write_text("# Skill\n", encoding="utf-8")
            (skill / "assets").mkdir()
            (skill / "assets" / "skill.txt").write_text("skill", encoding="utf-8")
            self.write_catalog(
                skill,
                [
                    {
                        "id": "overview",
                        "source": "README.md",
                        "optional": False,
                        "home": True,
                    }
                ],
            )

            (policy / "docs").mkdir(parents=True)
            (policy / "docs" / "index.md").write_text("# Policy\n", encoding="utf-8")
            (policy / "docs" / "assets").mkdir()
            (policy / "docs" / "assets" / "policy.txt").write_text(
                "asset",
                encoding="utf-8",
            )
            self.write_catalog(
                policy,
                [
                    {
                        "id": "overview",
                        "source": "docs/index.md",
                        "optional": False,
                        "home": True,
                    }
                ],
                [
                    {
                        "source": "docs/assets",
                        "destination": "assets",
                        "optional": False,
                    }
                ],
            )

            self.write_site(
                site,
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
                            "children": [
                                {
                                    "title": "Skill overview",
                                    "publication": "skill",
                                    "document": "overview",
                                    "destination": "skill/index.md",
                                }
                            ],
                        },
                        {
                            "title": "Policy",
                            "children": [
                                {
                                    "title": "Policy overview",
                                    "publication": "policy",
                                    "document": "overview",
                                    "destination": "policy/index.md",
                                }
                            ],
                        },
                    ],
                },
            )

            summary = assemble(
                {"site": site, "skill": skill, "policy": policy},
                site,
                output,
            )

            self.assertTrue((output / "docs" / "index.md").is_file())
            self.assertTrue((output / "docs" / "skill" / "index.md").is_file())
            self.assertTrue((output / "docs" / "policy" / "index.md").is_file())
            self.assertTrue((output / "docs" / "portal.txt").is_file())
            self.assertFalse((output / "docs" / "site" / "assets").exists())
            self.assertTrue(
                (output / "docs" / "skill" / "assets" / "skill.txt").is_file()
            )
            self.assertTrue(
                (output / "docs" / "policy" / "assets" / "policy.txt").is_file()
            )
            self.assertIn("publications: 3", summary)

    def test_manifest_must_cover_every_catalog_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            source = base / "source"
            output = base / "build"

            (site / "docs").mkdir(parents=True)
            (site / "docs" / "index.md").write_text("# Portal\n", encoding="utf-8")
            self.write_catalog(
                site,
                [
                    {
                        "id": "portal-home",
                        "source": "docs/index.md",
                        "optional": False,
                        "home": True,
                    }
                ],
            )

            source.mkdir()
            (source / "README.md").write_text("# Source\n", encoding="utf-8")
            (source / "EXTRA.md").write_text("# Extra\n", encoding="utf-8")
            self.write_catalog(
                source,
                [
                    {
                        "id": "overview",
                        "source": "README.md",
                        "optional": False,
                        "home": True,
                    },
                    {
                        "id": "extra",
                        "source": "EXTRA.md",
                        "optional": False,
                        "home": False,
                    },
                ],
            )

            self.write_site(
                site,
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
                            "title": "Source",
                            "publication": "source",
                            "document": "overview",
                            "destination": "source/index.md",
                        },
                    ],
                },
            )

            with self.assertRaisesRegex(
                AssemblyError,
                "does not cover publication documents: source:extra",
            ):
                assemble({"site": site, "source": source}, site, output)

    def test_site_home_must_be_first_and_generate_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            site = base / "site"
            output = base / "build"

            (site / "docs").mkdir(parents=True)
            (site / "docs" / "index.md").write_text("# Portal\n", encoding="utf-8")
            self.write_catalog(
                site,
                [
                    {
                        "id": "portal-home",
                        "source": "docs/index.md",
                        "optional": False,
                        "home": True,
                    }
                ],
            )
            self.write_site(
                site,
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
                            "destination": "portal.md",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(
                AssemblyError,
                "site home page must generate index.md",
            ):
                assemble({"site": site}, site, output)


if __name__ == "__main__":
    unittest.main()
