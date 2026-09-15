from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_audience_runtime import validate_projection_parity


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
            validate_projection_parity(root, model, self.expected())

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
            validate_projection_parity(root, model, self.expected())

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
                validate_projection_parity(root, model, self.expected())


if __name__ == "__main__":
    unittest.main()
