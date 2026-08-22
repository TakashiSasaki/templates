from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_publication.py"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "composition_publication_translation_classifier",
        VALIDATOR,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicationTranslationClassificationTests(unittest.TestCase):
    def test_parser_rejects_invalid_manifest_classification_inputs(self) -> None:
        validator = load_validator()
        cases = (
            (
                "wrong schema",
                {
                    "schema_version": 1,
                    "canonical_language": "en",
                    "translations": [],
                },
                "schema_version must be integer 2",
            ),
            (
                "wrong canonical language",
                {
                    "schema_version": 2,
                    "canonical_language": "ja",
                    "translations": [],
                },
                "canonical_language must be en",
            ),
            (
                "entry without path",
                {
                    "schema_version": 2,
                    "canonical_language": "en",
                    "translations": [{}],
                },
                "must declare a translation path",
            ),
            (
                "non Markdown path",
                {
                    "schema_version": 2,
                    "canonical_language": "en",
                    "translations": [{"translation": "translations/ja/data.json"}],
                },
                "translation must be Markdown",
            ),
            (
                "path outside translations root",
                {
                    "schema_version": 2,
                    "canonical_language": "en",
                    "translations": [{"translation": "docs/publication-catalog.md"}],
                },
                "must be beneath the translations directory",
            ),
            (
                "duplicate derivative path",
                {
                    "schema_version": 2,
                    "canonical_language": "en",
                    "translations": [
                        {"translation": "translations/ja/README.md"},
                        {"translation": "translations/ja/README.md"},
                    ],
                },
                "duplicate translation Markdown source",
            ),
        )

        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            for label, payload, diagnostic in cases:
                with self.subTest(case=label):
                    manifest.write_text(
                        json.dumps(payload),
                        encoding="utf-8",
                    )
                    with mock.patch.object(
                        validator,
                        "TRANSLATION_MANIFEST_PATH",
                        manifest,
                    ):
                        with self.assertRaisesRegex(
                            validator.PublicationError,
                            diagnostic,
                        ):
                            validator.parse_translation_classification()


if __name__ == "__main__":
    unittest.main()
