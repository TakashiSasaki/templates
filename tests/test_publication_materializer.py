from __future__ import annotations

import gzip
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
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

    def test_validate_written_payloads_detects_corrupt_bytes(self) -> None:
        import tempfile
        import generate_composition_playground_publication as playground_pub
        from composer_core_impl import CompositionError

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            manifest = {
                "schema_version": 2,
                "projection_id": "composition-playground-v1",
                "intent_projection_id": "composition-playground-intent-v1",
                "semantic_revision": "1" * 40,
                "semantic_objects": {path: "2" * 40 for path in playground_pub.SEMANTIC_PATHS},
                "assets": [playground_pub.BASE_NAME, playground_pub.INTENT_NAME],
            }
            (directory / playground_pub.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            (directory / playground_pub.BASE_NAME).write_bytes(b"corrupted-data")
            (directory / playground_pub.INTENT_NAME).write_bytes(b"corrupted-data")

            with self.assertRaises(CompositionError) as ctx:
                playground_pub.validate_written_payloads(
                    directory,
                    {playground_pub.BASE_NAME: b"expected-data", playground_pub.INTENT_NAME: b"expected-data"},
                    "1" * 40,
                )
            self.assertEqual("CORRUPT_PLAYGROUND_PUBLICATION", ctx.exception.code)

    def test_validate_written_payloads_detects_missing_file(self) -> None:
        import tempfile
        import generate_composition_playground_publication as playground_pub
        from composer_core_impl import CompositionError

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            manifest = {
                "schema_version": 2,
                "projection_id": "composition-playground-v1",
                "intent_projection_id": "composition-playground-intent-v1",
                "semantic_revision": "1" * 40,
                "semantic_objects": {path: "2" * 40 for path in playground_pub.SEMANTIC_PATHS},
                "assets": [playground_pub.BASE_NAME, playground_pub.INTENT_NAME],
            }
            (directory / playground_pub.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(CompositionError) as ctx:
                playground_pub.validate_written_payloads(
                    directory,
                    {playground_pub.BASE_NAME: b"expected-data"},
                    "1" * 40,
                )
            self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", ctx.exception.code)

    def test_standalone_check_directory_detects_missing_asset(self) -> None:
        import tempfile
        import generate_composition_playground_publication as playground_pub
        from composer_core_impl import CompositionError

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            manifest = {
                "schema_version": 2,
                "projection_id": "composition-playground-v1",
                "intent_projection_id": "composition-playground-intent-v1",
                "semantic_revision": "1" * 40,
                "semantic_objects": {path: "2" * 40 for path in playground_pub.SEMANTIC_PATHS},
                "assets": [playground_pub.BASE_NAME, playground_pub.INTENT_NAME],
            }
            (directory / playground_pub.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(CompositionError) as ctx:
                playground_pub.check_directory(directory)
            self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
