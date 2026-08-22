from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TranslationArtifactOverviewTests(unittest.TestCase):
    def test_repository_reader_translations_include_artifact_overviews(self) -> None:
        manifest = json.loads(
            (ROOT / "translations" / "manifest.json").read_text(encoding="utf-8")
        )
        reader_canonicals = {
            entry["canonical"]
            for entry in manifest["translations"]
            if "reader" in entry["surfaces"]
        }

        self.assertTrue(
            {
                "components/artifact.skill-core/files/README.md",
                "components/artifact.webapp-core/files/README.md",
            }.issubset(reader_canonicals)
        )


if __name__ == "__main__":
    unittest.main()
