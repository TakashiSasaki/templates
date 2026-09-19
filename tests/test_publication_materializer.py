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

    def test_materializer_descriptor_binds_the_semantic_revision(self) -> None:
        import generate_composition_playground_publication as publication
        revision = 'a' * 40
        self.assertEqual({'schema_version': 1, 'provider': 'composition',
                          'semantic_revision': revision},
                         json.loads(publication.publication_descriptor(revision)))
        self.assertEqual('publication-descriptor.json', publication.DESCRIPTOR_NAME)

    def test_refresh_descriptor_failure_preserves_all_previous_outputs(self) -> None:
        from unittest import mock
        import tempfile
        import materialize_publication as materializer
        import generate_composition_playground_publication as publication
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / 'generated'
            generated.mkdir()
            names = [publication.MANIFEST_NAME, publication.BASE_NAME,
                     publication.INTENT_NAME, 'publication-descriptor.json']
            before = {name: ('old-' + name).encode() for name in names}
            for name, data in before.items(): (generated / name).write_bytes(data)
            write = publication._atomic_write
            write_text = Path.write_text
            def fail_atomic(path, data):
                if 'publication-descriptor' in path.name: raise OSError('descriptor write failed')
                write(path, data)
            def fail_text(path, *args, **kwargs):
                if 'publication-descriptor' in path.name: raise OSError('descriptor write failed')
                return write_text(path, *args, **kwargs)
            with mock.patch.object(materializer, 'ROOT', root), mock.patch.object(
                materializer, 'ensure_runtime_dependencies', return_value=None
            ), mock.patch.object(sys, 'argv', ['materialize_publication.py', '--source-root', str(root), '--refresh']), mock.patch.object(
                publication, 'current_semantic_snapshot', return_value=('a' * 40, {})
            ), mock.patch.object(publication, 'publication_payloads', return_value={publication.BASE_NAME: b'new-base', publication.INTENT_NAME: b'new-intent'}), mock.patch.object(
                publication, 'validate_written_payloads'
            ), mock.patch.object(publication, '_atomic_write', side_effect=fail_atomic), mock.patch.object(Path, 'write_text', fail_text):
                self.assertEqual(1, materializer.main())
            self.assertEqual(before, {name: (generated / name).read_bytes() for name in names})


if __name__ == "__main__":
    unittest.main()
