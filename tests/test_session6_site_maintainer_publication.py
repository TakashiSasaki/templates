from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.assemble_publications import load_manifest, pages
from scripts.assemble_publications_v3 import load_catalog
from scripts.reader_navigation_locales import load_overlays


ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "site-maintenance": ("MAINTENANCE.md", "maintain/site/maintenance.md"),
    "authority-model": ("docs/authority-model.md", "maintain/site/authority-model.md"),
    "integrated-publication": ("PUBLISHING.md", "maintain/publication/integrated-publication.md"),
    "publication-staging": ("PUBLICATION_STAGING.md", "maintain/publication/staging.md"),
    "publication-freshness": ("PUBLICATION_FRESHNESS.md", "maintain/publication/provider-freshness.md"),
    "runtime-freshness": ("FRESHNESS.md", "maintain/site/runtime-freshness.md"),
    "glossary-contract": ("GLOSSARY.md", "maintain/publication/glossary.md"),
    "language-contract": ("LANGUAGE.md", "maintain/publication/language.md"),
    "site-pwa-contract": ("PWA.md", "maintain/site/pwa.md"),
    "ci-performance": ("docs/ci/site-performance.md", "maintain/qualification/ci-performance.md"),
}


class Session6SiteMaintainerPublicationTests(unittest.TestCase):
    def test_all_architecture_s_site_candidates_are_canonical_maintain_documents(self):
        catalog, _ = load_catalog("site", ROOT)
        manifest = json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))
        documents = {entry["document"]: entry for entry in manifest["documents"] if entry["publication"] == "site"}

        for identifier, (source, destination) in EXPECTED.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(catalog[identifier]["source"].as_posix(), source)
                self.assertEqual(documents[identifier]["destination"], destination)
                self.assertEqual(documents[identifier]["primary_audience"], "maintain")
                self.assertEqual(documents[identifier]["additional_audiences"], [])

    def test_each_candidate_has_one_maintain_navigation_membership_and_localized_chrome(self):
        navigation = load_manifest(ROOT / "site-manifest.json").navigation
        maintain = [page for page in pages(navigation["maintain"]) if page["publication"] == "site"]
        membership = [page["document"] for page in maintain if page["document"] in EXPECTED]
        self.assertEqual(set(membership), set(EXPECTED))
        self.assertEqual(len(membership), len(EXPECTED))
        load_overlays(ROOT / "reader-navigation-locales.json", navigation)
