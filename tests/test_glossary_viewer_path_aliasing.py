from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.generate_glossary_viewer import GlossaryViewerError, generate


REVISION = "a" * 40


def integrated_model() -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": "TakashiSasaki/templates",
        "terms": [
            {
                "id": "templates-example",
                "term": "Example",
                "aliases": [],
                "origin": "repository",
                "definition": "Canonical definition.",
                "provider": "site",
                "source_path": "docs/glossary.yml",
                "source_revision": REVISION,
            }
        ],
    }


class GlossaryViewerPathAliasingTests(unittest.TestCase):
    def write_input(self, root: Path) -> Path:
        path = root / "index.json"
        path.write_text(json.dumps(integrated_model()), encoding="utf-8")
        return path

    def test_identical_input_and_output_path_is_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = self.write_input(Path(directory))
            original = input_path.read_bytes()

            with self.assertRaisesRegex(
                GlossaryViewerError,
                "input and output must refer to different files",
            ):
                generate(input_path, input_path)

            self.assertEqual(original, input_path.read_bytes())

    def test_hard_link_output_to_input_is_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = self.write_input(root)
            output_path = root / "index.html"
            try:
                os.link(input_path, output_path)
            except OSError as exc:
                self.skipTest(f"hard links are not supported here: {exc}")
            original = input_path.read_bytes()

            with self.assertRaisesRegex(
                GlossaryViewerError,
                "input and output must refer to different files",
            ):
                generate(input_path, output_path)

            self.assertEqual(original, input_path.read_bytes())
            self.assertEqual(original, output_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
