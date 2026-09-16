from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from scripts.assemble_publications import load_manifest, pages
from scripts.materialize_publication_staging import materialize
from scripts.publish_translations import publish_translations, TranslationPublicationError
from tests.publication_context import publication_root
from tests.test_publication_staging import (
    FUTURE_ID,
    _configure_future_mapping,
    _copy_inputs,
)


ROOT = Path(__file__).resolve().parents[1]


class PublicationStagingQualificationTests(unittest.TestCase):
    def test_translation_integration_uses_returned_staged_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            pristine = base / "pristine"
            provider = base / "provider"
            pristine.mkdir()
            _copy_inputs(pristine)
            _configure_future_mapping(pristine)
            staging_path = pristine / "publication-staging.json"
            data = json.loads(staging_path.read_text(encoding="utf-8"))
            mapping = data["mappings"][0]
            mapping["publication"] = "composition"
            mapping["insert_after"] = {
                "publication": "composition",
                "document": "publication-boundary",
            }
            staging_path.write_text(json.dumps(data), encoding="utf-8")

            (provider / "docs").mkdir(parents=True)
            (provider / "translations/ja/docs").mkdir(parents=True)
            canonical = b"# Index\n"
            (provider / "docs/index.md").write_bytes(canonical)
            (provider / "docs/future.md").write_text("# Future\n", encoding="utf-8")
            (provider / "translations/ja/docs/index.md").write_text(
                "# Index\n\n> **参考訳（非正本）:** test\n\n"
                "[Future](../../../docs/future.md)\n",
                encoding="utf-8",
            )
            (provider / "translations/manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "canonical_language": "en",
                        "translations": [
                            {
                                "canonical": "docs/index.md",
                                "language": "ja",
                                "translation": "translations/ja/docs/index.md",
                                "canonical_blob_sha": hashlib.sha1(
                                    b"blob "
                                    + str(len(canonical)).encode()
                                    + b"\0"
                                    + canonical
                                ).hexdigest(),
                                "surfaces": ["reader"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            documents = {
                "documentation-index": {
                    "source": PurePosixPath("docs/index.md"),
                    "optional": False,
                    "home": False,
                },
                FUTURE_ID: {
                    "source": PurePosixPath("docs/future.md"),
                    "optional": False,
                    "home": False,
                },
            }

            def publish(output: Path):
                _, navigation = load_manifest(
                    publication_root(pristine) / "site-manifest.json"
                )
                selected = [
                    page
                    for page in pages(navigation)
                    if page["publication"] == "composition"
                    and page["document"] in documents
                ]
                return publish_translations(
                    {"composition": (provider, documents, [])},
                    selected,
                    output,
                )

            with mock.patch.dict(os.environ, {"SITE_PUBLICATION_ROOT": str(pristine)}):
                with self.assertRaisesRegex(TranslationPublicationError, "does not resolve"):
                    publish(base / "before")

            staged_root = materialize(pristine, FUTURE_ID)
            with mock.patch.dict(os.environ, {"SITE_PUBLICATION_ROOT": str(staged_root)}):
                records = publish(base / "after")

            self.assertEqual(1, len(records))
            output = base / "after" / records[0].translation_destination
            self.assertIn("future-policy-page.md", output.read_text(encoding="utf-8"))
            self.assertNotEqual(
                (pristine / "site-manifest.json").read_bytes(),
                (staged_root / "site-manifest.json").read_bytes(),
            )

    def test_explicit_missing_publication_root_fails_closed(self) -> None:
        with mock.patch.dict(os.environ, {"SITE_PUBLICATION_ROOT": ""}):
            with self.assertRaises(ValueError):
                publication_root(ROOT)

    def test_reusable_build_consumes_materializer_snapshot_before_tests(self) -> None:
        workflow = (ROOT / '.github/workflows/site-producer.yml').read_text()
        producer = (Path(__file__).resolve().parents[1] / 'integration/producer.py').read_text()
        self.assertIn('stage_models(',producer)
        self.assertLess(producer.index('stage_models('),producer.index('build_bundle(') if 'build_bundle(' in producer else producer.index("with tempfile.TemporaryDirectory"))
        self.assertIn('--staging-ids "${STAGING_IDS:-$STAGING_ID}"',workflow)
        self.assertNotIn('SITE_PUBLICATION_ROOT=',workflow)
        self.assertNotIn('publication_staging_id', (ROOT / '.github/workflows/deploy-pages.yml').read_text())


if __name__ == "__main__":
    unittest.main()
