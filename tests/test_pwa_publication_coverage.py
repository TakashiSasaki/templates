from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_publication.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("composition_publication_validator", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PwaPublicationCoverageTests(unittest.TestCase):
    def test_pwa_decision_record_is_reader_material(self) -> None:
        validator = load_validator()
        self.assertIn("PWA.md", validator.READER_BASENAMES)
        self.assertTrue(validator.reader_material("files/PWA.md"))
        self.assertFalse(validator.reader_material("files/contracts/pwa-manifest.json"))


if __name__ == "__main__":
    unittest.main()
