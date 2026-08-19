from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_freshness_metadata  # noqa: E402


SITE_REVISION = "a" * 40
PUBLICATIONS = {
    "composition": "b" * 40,
    "policy": "c" * 40,
}
DEPLOYMENT_TIMESTAMP = "2026-08-15 22:07:00 JST"


def annotated_page() -> str:
    return (
        "<html><head>"
        f'<meta name="templates-site-revision" content="{SITE_REVISION}">'
        "</head><body></body></html>"
    )


class FreshnessContractVerifierTests(unittest.TestCase):
    def test_rejects_on_disk_payload_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            (site_root / "index.html").write_text(annotated_page(), encoding="utf-8")
            expected = generate_freshness_metadata.build_payload(
                SITE_REVISION,
                DEPLOYMENT_TIMESTAMP,
                PUBLICATIONS,
            )
            output = site_root / "site-version.json"
            altered = dict(expected)
            altered["deployed_at"] = None
            output.write_text(
                json.dumps(altered, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                generate_freshness_metadata.FreshnessMetadataError,
                "payload verification failed",
            ):
                generate_freshness_metadata.verify_freshness_contract(
                    site_root,
                    output,
                    SITE_REVISION,
                    expected,
                )

    def test_rejects_type_coercible_schema_version_values(self) -> None:
        expected = generate_freshness_metadata.build_payload(
            SITE_REVISION,
            DEPLOYMENT_TIMESTAMP,
            PUBLICATIONS,
        )
        for raw_schema_version in ("true", "1.0"):
            with self.subTest(raw_schema_version=raw_schema_version):
                with tempfile.TemporaryDirectory() as directory:
                    site_root = Path(directory)
                    (site_root / "index.html").write_text(
                        annotated_page(),
                        encoding="utf-8",
                    )
                    canonical = generate_freshness_metadata.canonical_payload_text(expected)
                    output = site_root / "site-version.json"
                    output.write_text(
                        canonical.replace(
                            '"schema_version": 1',
                            f'"schema_version": {raw_schema_version}',
                            1,
                        ),
                        encoding="utf-8",
                    )

                    with self.assertRaisesRegex(
                        generate_freshness_metadata.FreshnessMetadataError,
                        "payload verification failed",
                    ):
                        generate_freshness_metadata.verify_freshness_contract(
                            site_root,
                            output,
                            SITE_REVISION,
                            expected,
                        )

    def test_rejects_when_only_sandbox_preview_html_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site_root = Path(directory)
            preview = site_root / "repository-trees/previews/composition/revision"
            preview.mkdir(parents=True)
            (preview / "preview.html").write_text(
                "<html><head></head><body>preview</body></html>",
                encoding="utf-8",
            )
            expected = generate_freshness_metadata.build_payload(
                SITE_REVISION,
                DEPLOYMENT_TIMESTAMP,
                PUBLICATIONS,
            )
            output = site_root / "site-version.json"
            output.write_text(
                generate_freshness_metadata.canonical_payload_text(expected),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                generate_freshness_metadata.FreshnessMetadataError,
                "no cache-eligible HTML freshness metadata verified",
            ):
                generate_freshness_metadata.verify_freshness_contract(
                    site_root,
                    output,
                    SITE_REVISION,
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
