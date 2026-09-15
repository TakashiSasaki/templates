from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from scripts.check_audience_runtime import (
    catalog_optional_destinations,
    validate_projection_parity,
)


class AudienceRuntimeProjectionParityTests(unittest.TestCase):
    def expected(self) -> dict:
        return {
            "documents": {
                "index.md": {"primary": "use"},
                "optional/index.md": {"primary": "maintain"},
            },
            "routes": {
                "/": "index.md",
                "/index.html": "index.md",
                "/optional/": "optional/index.md",
                "/optional/index.html": "optional/index.md",
            },
        }

    def write_reader_runtime(
        self,
        root: Path,
        routes: dict[str, str] | None = None,
    ) -> None:
        payload = {
            "schema_version": 1,
            "locales": [
                {"language": "ja", "labels": {}, "routes": routes or {}}
            ],
        }
        (root / "reader-navigation-runtime.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_optional_document_omission_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_reader_runtime(root)
            model = {
                "documents": {"index.md": {"primary": "use"}},
                "routes": {"/": "index.md", "/index.html": "index.md"},
            }
            validate_projection_parity(
                root, model, self.expected(), {"optional/index.md"}
            )

    def test_required_document_omission_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_reader_runtime(root)
            model = {
                "documents": {"index.md": {"primary": "use"}},
                "routes": {"/": "index.md", "/index.html": "index.md"},
            }
            with self.assertRaisesRegex(
                AssertionError, "missing required audience documents"
            ):
                validate_projection_parity(root, model, self.expected(), set())

    def test_generated_manifest_document_is_not_looked_up_or_optional(self) -> None:
        manifest = SimpleNamespace(
            documents=[
                {
                    "publication": "site",
                    "document": "optional-provider-document",
                    "destination": "optional/index.md",
                },
                {
                    "publication": "site",
                    "document": "generated-repository-trees",
                    "destination": "repository-trees/index.md",
                },
            ]
        )
        catalogs = {
            "site": {
                "optional-provider-document": SimpleNamespace(optional=True),
            }
        }

        self.assertEqual(
            catalog_optional_destinations(manifest, catalogs),
            {"optional/index.md"},
        )

    def test_actual_translation_aliases_form_the_only_route_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            translated = root / "ja"
            translated.mkdir()
            (translated / "index.html").write_text("translated", encoding="utf-8")
            self.write_reader_runtime(root, {"/": "/ja/"})
            model = {
                "documents": {"index.md": {"primary": "use"}},
                "routes": {
                    "/": "index.md",
                    "/index.html": "index.md",
                    "/ja/": "index.md",
                    "/ja/index.html": "index.md",
                },
            }
            validate_projection_parity(
                root, model, self.expected(), {"optional/index.md"}
            )

    def test_uninventoried_route_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_reader_runtime(root)
            model = {
                "documents": {"index.md": {"primary": "use"}},
                "routes": {
                    "/": "index.md",
                    "/index.html": "index.md",
                    "/fabricated/": "index.md",
                },
            }
            with self.assertRaisesRegex(
                AssertionError, "assembled audience route projection drift"
            ):
                validate_projection_parity(
                    root, model, self.expected(), {"optional/index.md"}
                )


if __name__ == "__main__":
    unittest.main()
