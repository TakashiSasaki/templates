"""Canonical source can advance before its optional reference translation."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "translation_status", ROOT / "scripts/check_translation_status.py"
)
status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(status)


class TranslationStatusTests(unittest.TestCase):
    def test_new_source_missing_translation_and_later_updates_need_no_translation_edit(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "translations/ja").mkdir(parents=True)
            source = root / "README.md"
            source.write_text("# Original\n")
            catalog = {"documents": [{"id": "home", "source": "README.md"}]}
            (root / "docs/publication-catalog.json").write_text(json.dumps(catalog))
            self.assertEqual(status.report(root)["summary"]["missing"], 1)
            translation = root / "translations/ja/README.md"
            translation.write_text("# 参考訳\n")
            manifest = {
                "translations": [
                    {
                        "canonical": "README.md",
                        "translation": "translations/ja/README.md",
                        "language": "ja",
                        "surfaces": ["reader"],
                        "canonical_blob_sha": status.blob(source),
                    }
                ]
            }
            manifest_path = root / "translations/manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            evidence = manifest_path.read_bytes()
            self.assertEqual(status.report(root)["summary"]["current"], 1)
            source.write_text("# New canonical meaning\n")
            self.assertEqual(status.report(root)["summary"]["stale"], 1)
            self.assertEqual(manifest_path.read_bytes(), evidence)
            translation.unlink()
            self.assertEqual(status.report(root)["summary"]["missing"], 1)
            (root / "docs/publication-catalog.json").write_text(
                json.dumps({"documents": []})
            )
            self.assertEqual(status.report(root)["records"], [])


if __name__ == "__main__":
    unittest.main()
