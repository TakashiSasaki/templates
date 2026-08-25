from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_freshness_metadata  # noqa: E402


SITE_REVISION = "a" * 40
PUBLICATIONS = {
    "composition": "b" * 40,
    "policy": "c" * 40,
}
DEPLOYMENT_TIMESTAMP = "2026-08-26 07:00:00 JST"


def page(body: str = "page") -> str:
    return f"<html><head><title>Test</title></head><body>{body}</body></html>"


class FreshnessMetadataSingleValidationTests(unittest.TestCase):
    def test_annotation_does_not_reparse_the_in_memory_inserted_document(self) -> None:
        with mock.patch.object(
            generate_freshness_metadata,
            "freshness_revision_metas",
            side_effect=AssertionError("unexpected in-memory reparse"),
        ):
            updated = generate_freshness_metadata.annotate_site_revision(
                page(),
                SITE_REVISION,
                Path("index.html"),
            )

        self.assertIn(
            '<meta name="templates-site-revision" '
            f'content="{SITE_REVISION}">',
            updated,
        )

    def test_final_on_disk_verifier_rejects_a_bad_injected_revision(self) -> None:
        wrong_revision = "d" * 40

        def corrupt_annotation(source: str, revision: str, path: Path) -> str:
            del revision, path
            marker = (
                '<meta name="templates-site-revision" '
                f'content="{wrong_revision}">\n'
            )
            return source.replace("</head>", marker + "</head>", 1)

        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            (site_root / "index.html").write_text(page(), encoding="utf-8")

            with mock.patch.object(
                generate_freshness_metadata,
                "annotate_site_revision",
                side_effect=corrupt_annotation,
            ):
                with self.assertRaisesRegex(
                    generate_freshness_metadata.FreshnessMetadataError,
                    "freshness revision metadata verification failed",
                ):
                    generate_freshness_metadata.generate_freshness_metadata(
                        site_root,
                        SITE_REVISION,
                        DEPLOYMENT_TIMESTAMP,
                        PUBLICATIONS,
                    )

    def test_generation_keeps_independent_final_html_rediscovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            (site_root / "index.html").write_text(page(), encoding="utf-8")
            original_discovery = generate_freshness_metadata.generated_html_files

            with mock.patch.object(
                generate_freshness_metadata,
                "generated_html_files",
                wraps=original_discovery,
            ) as discovery:
                generate_freshness_metadata.generate_freshness_metadata(
                    site_root,
                    SITE_REVISION,
                    DEPLOYMENT_TIMESTAMP,
                    PUBLICATIONS,
                )

            self.assertEqual(2, discovery.call_count)


if __name__ == "__main__":
    unittest.main()
