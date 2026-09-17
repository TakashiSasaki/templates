from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import publication_export


class PublicationExportTests(unittest.TestCase):
    def test_current_export_is_bounded_and_valid(self):
        publication_export.validate(ROOT)


if __name__ == "__main__":
    unittest.main()
