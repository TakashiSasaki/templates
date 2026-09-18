from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import publication_export


class PublicationExportTests(unittest.TestCase):
    def test_current_export_is_bounded_and_valid(self):
        publication_export.validate(ROOT)

    def test_record_export_separates_subject_ownership_from_local_metadata(self):
        declaration = json.loads((ROOT / "docs/publication-capabilities.json").read_text())
        record = next(item for item in declaration["exports"] if item["kind"] == "record")
        self.assertEqual(record["subject_ownership"], "external-as-recorded")
        self.assertEqual(record["redistribution"], "local-record-metadata")
        self.assertNotIn("rights", record)

    def test_reference_only_payload_or_non_record_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "modeling"
            shutil.copytree(ROOT, root)
            declaration_path = root / "docs/publication-capabilities.json"
            declaration = json.loads(declaration_path.read_text())
            record = next(item for item in declaration["exports"] if item["kind"] == "record")
            record["redistribution"] = "reference-only"
            declaration_path.write_text(json.dumps(declaration), encoding="utf-8")
            with self.assertRaises(publication_export.ExportError):
                publication_export.validate(root)

            declaration["exports"] = [item for item in declaration["exports"] if item["kind"] != "record"]
            declaration_path.write_text(json.dumps(declaration), encoding="utf-8")
            with self.assertRaises(publication_export.ExportError):
                publication_export.validate(root)


if __name__ == "__main__":
    unittest.main()
