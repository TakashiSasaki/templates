from __future__ import annotations

import gzip
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "materialize_publication.py"
GENERATED = ROOT / "generated"


class PublicationMaterializerTests(unittest.TestCase):
    def test_conventional_entrypoint_materializes_deterministic_playground_assets(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--source-root", str(ROOT)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("materialized Composition publication assets for", result.stdout)

        manifest = json.loads(
            (GENERATED / "composition-playground-publication.json").read_text(encoding="utf-8")
        )
        for name, projection_id in (
            ("composition-playground-v1.json.gz", "composition-playground-v1"),
            ("composition-playground-intent-v1.json.gz", "composition-playground-intent-v1"),
        ):
            payload = (GENERATED / name).read_bytes()
            self.assertEqual(b"\x1f\x8b", payload[:2])
            projection = json.loads(gzip.decompress(payload))
            self.assertEqual(projection_id, projection["projection_id"])
            self.assertEqual(manifest["semantic_revision"], projection["source"]["revision"])

    def test_entrypoint_rejects_a_different_source_root(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--source-root", str(ROOT.parent)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("PUBLICATION_ROOT_MISMATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
