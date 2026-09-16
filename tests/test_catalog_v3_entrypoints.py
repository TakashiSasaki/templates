from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import assemble_publications, assemble_publications_v3


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-producer.yml"
TRANSLATION_PUBLISHER = ROOT / "scripts/publish_provider_translations.py"


class CatalogV3EntrypointTests(unittest.TestCase):
    def test_pages_build_uses_stable_v3_alias(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn('scripts/produce_publication_bundle.py',workflow)
        self.assertIn('scripts/render_publication_bundle.py',workflow)
        self.assertNotIn('scripts/assemble_publications_v3.py',workflow)

    def test_stable_v3_entrypoint_reexports_canonical_contract_symbols(self) -> None:
        self.assertIs(
            assemble_publications_v3.AssemblyError,
            assemble_publications.AssemblyError,
        )
        self.assertIs(
            assemble_publications_v3.load_catalog,
            assemble_publications.load_catalog,
        )
        self.assertIsNot(
            assemble_publications_v3.main,
            assemble_publications.main,
        )

    def test_stable_v3_entrypoint_rebases_publication_links(self) -> None:
        source = (ROOT / "scripts/assemble_publications_v3.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "from scripts.publication_link_rewriter import rebase_publication_links",
            source,
        )
        self.assertIn("publication links rebased", source)

    def test_non_site_assembly_does_not_require_site_source_root(self) -> None:
        argv = [
            "assemble_publications_v3.py",
            "--publication",
            "composition=/tmp/composition",
            "--site-root",
            "/tmp/site",
            "--output-root",
            "/tmp/output",
        ]
        with (
            patch("sys.argv", argv),
            patch.object(
                assemble_publications_v3,
                "parse_publications",
                return_value={"composition": Path("/tmp/composition")},
            ),
            patch.object(assemble_publications_v3, "assemble", return_value=[]),
            patch.object(
                assemble_publications_v3,
                "rebase_publication_links",
                return_value=0,
            ) as rebase,
        ):
            self.assertEqual(assemble_publications_v3.main(), 0)

        self.assertIsNone(rebase.call_args.kwargs["site_source_root"])

    def test_site_assembly_requires_source_root_before_mutation(self) -> None:
        argv = [
            "assemble_publications_v3.py",
            "--publication",
            "site=/tmp/site-publication",
            "--site-root",
            "/tmp/site",
            "--output-root",
            "/tmp/output",
        ]
        with (
            patch("sys.argv", argv),
            patch.object(
                assemble_publications_v3,
                "parse_publications",
                return_value={"site": Path("/tmp/site-publication")},
            ),
            patch.object(assemble_publications_v3, "assemble") as assemble,
            patch.object(
                assemble_publications_v3,
                "rebase_publication_links",
            ) as rebase,
        ):
            self.assertEqual(assemble_publications_v3.main(), 1)

        assemble.assert_not_called()
        rebase.assert_not_called()

    def test_translation_publisher_uses_stable_v3_alias(self) -> None:
        source = TRANSLATION_PUBLISHER.read_text(encoding="utf-8")

        self.assertIn(
            "from scripts.assemble_publications_v3 import load_catalog",
            source,
        )
        self.assertIn(
            "from scripts.assemble_publications import load_manifest, pages, parse_publications",
            source,
        )


if __name__ == "__main__":
    unittest.main()
