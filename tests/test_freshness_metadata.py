from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_freshness_metadata  # noqa: E402
import write_publication_provenance  # noqa: E402


SITE_REVISION = "a" * 40
PUBLICATIONS = {
    "skill": "b" * 40,
    "policy": "c" * 40,
    "webapp": "d" * 40,
}
DEPLOYMENT_TIMESTAMP = "2026-08-15 22:07:00 JST"


def page(body: str = "page") -> str:
    return f"<html><head><title>Test</title></head><body>{body}</body></html>"


class FreshnessMetadataTests(unittest.TestCase):
    def test_generates_identity_and_annotates_non_preview_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            nested = site_root / "guide"
            preview = site_root / "repository-trees/previews/skill/revision"
            nested.mkdir()
            preview.mkdir(parents=True)
            (site_root / "index.html").write_text(page(), encoding="utf-8")
            (nested / "index.html").write_text(page("guide"), encoding="utf-8")
            preview_page = preview / "preview.html"
            preview_page.write_text(page("preview"), encoding="utf-8")

            output, annotated = generate_freshness_metadata.generate_freshness_metadata(
                site_root,
                SITE_REVISION,
                DEPLOYMENT_TIMESTAMP,
                PUBLICATIONS,
            )

            self.assertEqual(site_root / "site-version.json", output)
            self.assertEqual(2, annotated)
            self.assertEqual(
                {
                    "schema_version": 1,
                    "site_revision": SITE_REVISION,
                    "deployed_at": DEPLOYMENT_TIMESTAMP,
                    "publications": PUBLICATIONS,
                },
                json.loads(output.read_text(encoding="utf-8")),
            )
            marker = (
                '<meta name="templates-site-revision" '
                f'content="{SITE_REVISION}">'
            )
            self.assertIn(marker, (site_root / "index.html").read_text(encoding="utf-8"))
            self.assertIn(marker, (nested / "index.html").read_text(encoding="utf-8"))
            self.assertNotIn(
                "templates-site-revision",
                preview_page.read_text(encoding="utf-8"),
            )

    def test_preview_build_records_unknown_deployment_time(self) -> None:
        payload = generate_freshness_metadata.build_payload(
            SITE_REVISION,
            "",
            PUBLICATIONS,
        )
        self.assertIsNone(payload["deployed_at"])

    def test_conflicting_revision_metadata_is_rejected(self) -> None:
        source = (
            "<html><head>"
            '<meta name="templates-site-revision" content="'
            + "e" * 40
            + '">'
            "</head><body></body></html>"
        )
        with self.assertRaises(generate_freshness_metadata.FreshnessMetadataError):
            generate_freshness_metadata.annotate_site_revision(
                source,
                SITE_REVISION,
                Path("index.html"),
            )

    def test_missing_provider_revision_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            generate_freshness_metadata.FreshnessMetadataError,
            "missing publication revision",
        ):
            generate_freshness_metadata.build_payload(
                SITE_REVISION,
                DEPLOYMENT_TIMESTAMP,
                {"skill": PUBLICATIONS["skill"]},
            )

    def test_reads_deployed_and_preview_notices_from_rendered_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            index = site_root / "index.html"
            index.write_text(
                page(f"Deployment time: {DEPLOYMENT_TIMESTAMP}"),
                encoding="utf-8",
            )
            self.assertEqual(
                DEPLOYMENT_TIMESTAMP,
                generate_freshness_metadata.deployment_timestamp_from_index(site_root),
            )

            index.write_text(page("Preview build (not deployed)"), encoding="utf-8")
            self.assertEqual(
                "",
                generate_freshness_metadata.deployment_timestamp_from_index(site_root),
            )

    def test_provenance_projection_generates_client_freshness_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            output = site_root / "build-provenance.json"
            (site_root / "index.html").write_text(
                page(f"Deployment time: {DEPLOYMENT_TIMESTAMP}"),
                encoding="utf-8",
            )

            write_publication_provenance.write_provenance(
                output,
                "TakashiSasaki/templates",
                SITE_REVISION,
                PUBLICATIONS,
            )
            result = write_publication_provenance.project_freshness_metadata(
                output,
                SITE_REVISION,
                PUBLICATIONS,
            )

            self.assertIsNotNone(result)
            site_version, annotated = result
            self.assertEqual(1, annotated)
            payload = json.loads(site_version.read_text(encoding="utf-8"))
            self.assertEqual(SITE_REVISION, payload["site_revision"])
            self.assertEqual(DEPLOYMENT_TIMESTAMP, payload["deployed_at"])


if __name__ == "__main__":
    unittest.main()
