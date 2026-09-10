from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_publication_assets import (
    STAMP_FILE,
    _SUCCESSFUL_MATERIALIZATIONS,
    PublicationMaterializationError,
    is_publication_materialized,
    materialize_publication,
)


class PublicationMaterializationTests(unittest.TestCase):
    def write_catalog(self, root: Path, *, version: int, source_kind: str | None) -> None:
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        asset = {
            "source": "generated/output.bin",
            "destination": "runtime/output.bin",
            "optional": False,
        }
        if source_kind is not None:
            asset["source_kind"] = source_kind
        catalog = {
            "schema_version": version,
            "documents": [
                {
                    "id": "overview",
                    "source": "README.md",
                    "optional": False,
                    "home": True,
                }
            ],
            "assets": [asset],
        }
        path = root / "docs" / "publication-catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(catalog), encoding="utf-8")

    def write_materializer(self, root: Path, *, fail: bool = False) -> None:
        path = root / "scripts" / "materialize_publication.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        common = """from __future__ import annotations
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
args = parser.parse_args()
counter = args.source_root / 'materializer-runs.txt'
count = int(counter.read_text(encoding='utf-8')) + 1 if counter.exists() else 1
counter.write_text(str(count), encoding='utf-8')
"""
        if fail:
            body = common + "import sys\nprint('fixture failure', file=sys.stderr)\nraise SystemExit(7)\n"
        else:
            body = common + """target = args.source_root / 'generated' / 'output.bin'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(b'deterministic fixture output')
"""
        path.write_text(body, encoding="utf-8")

    def test_v4_generated_asset_materializes_then_passes_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(
                b"deterministic fixture output",
                (root / "generated" / "output.bin").read_bytes(),
            )

    def test_v4_generated_asset_without_materializer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "declares generated publication assets",
            ):
                materialize_publication(root, "fixture")

    def test_materializer_failure_is_not_treated_as_optional_or_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root, fail=True)
            for expected_runs in (1, 2):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "publication materializer failed: fixture failure",
                ):
                    materialize_publication(root, "fixture")
                self.assertEqual(
                    str(expected_runs),
                    (root / "materializer-runs.txt").read_text(encoding="utf-8"),
                )

    def test_v4_success_is_reused_but_revalidated_and_invalidated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertFalse(materialize_publication(root, "fixture"))
            self.assertEqual(
                "1",
                (root / "materializer-runs.txt").read_text(encoding="utf-8"),
            )

            # A cached success never suppresses strict post-validation. If a
            # generated product disappears, the provider materializer runs again.
            (root / "generated" / "output.bin").unlink()
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(
                "2",
                (root / "materializer-runs.txt").read_text(encoding="utf-8"),
            )

            # In-place lifecycle input changes invalidate the root cache entry.
            catalog = root / "docs" / "publication-catalog.json"
            catalog.write_text(catalog.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(
                "3",
                (root / "materializer-runs.txt").read_text(encoding="utf-8"),
            )

    def test_v3_conventional_materializer_is_supported_only_as_migration_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=3, source_kind=None)
            self.write_materializer(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue((root / "generated" / "output.bin").is_file())

    def test_v3_without_materializer_retains_existing_strict_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=3, source_kind=None)
            self.assertFalse(is_publication_materialized(root, "fixture"))
            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "declared asset source does not exist",
            ):
                materialize_publication(root, "fixture")

            # When the required asset exists, is_publication_materialized returns True
            (root / "README.md").write_text("content", encoding="utf-8")
            out = root / "generated" / "output.bin"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"content")
            self.assertTrue(is_publication_materialized(root, "fixture"))

    def test_process_crossing_reuse_with_persistent_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)

            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))
            self.assertTrue((root / STAMP_FILE).is_file())
            self.assertEqual("1", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

            # Simulate new process by clearing process-local in-memory cache
            _SUCCESSFUL_MATERIALIZATIONS.clear()

            # Second call in new process reuses persistent stamp without re-running materializer
            self.assertFalse(materialize_publication(root, "fixture"))
            self.assertEqual("1", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

    def test_persistent_stamp_invalidated_by_corrupted_generated_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("1", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

            # Corrupt generated asset
            (root / "generated" / "output.bin").write_bytes(b"tampered content")
            _SUCCESSFUL_MATERIALIZATIONS.clear()

            # Re-running materializer is triggered to recover valid state
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("2", (root / "materializer-runs.txt").read_text(encoding="utf-8"))
            self.assertEqual(b"deterministic fixture output", (root / "generated" / "output.bin").read_bytes())

    def test_persistent_stamp_invalidated_by_corrupted_stamp_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("1", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

            # Corrupt stamp file with malformed content
            (root / STAMP_FILE).write_text("invalid-json{", encoding="utf-8")
            _SUCCESSFUL_MATERIALIZATIONS.clear()

            # Materializer re-runs and regenerates stamp
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("2", (root / "materializer-runs.txt").read_text(encoding="utf-8"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

    def test_persistent_stamp_invalidated_by_materializer_script_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("1", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

            # Modify materializer script
            mat = root / "scripts" / "materialize_publication.py"
            mat.write_text(mat.read_text(encoding="utf-8") + "\n# updated\n", encoding="utf-8")
            _SUCCESSFUL_MATERIALIZATIONS.clear()

            # Materializer re-runs
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("2", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

    def test_persistent_stamp_generated_directory_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            catalog = {
                "schema_version": 4,
                "documents": [
                    {
                        "id": "overview",
                        "source": "README.md",
                        "optional": False,
                        "home": True,
                    }
                ],
                "assets": [
                    {
                        "source": "generated/bundle",
                        "destination": "runtime/bundle",
                        "optional": False,
                        "source_kind": "generated",
                    }
                ],
            }
            path = root / "docs" / "publication-catalog.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(catalog), encoding="utf-8")

            mat = root / "scripts" / "materialize_publication.py"
            mat.parent.mkdir(parents=True, exist_ok=True)
            mat.write_text(
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "out = args.source_root / 'generated' / 'bundle'\n"
                "out.mkdir(parents=True, exist_ok=True)\n"
                "(out / 'a.bin').write_bytes(b'alpha')\n"
                "(out / 'b.bin').write_bytes(b'beta')\n",
                encoding="utf-8",
            )

            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

            stamp_data = json.loads((root / STAMP_FILE).read_text(encoding="utf-8"))
            self.assertIn("generated/bundle/a.bin", stamp_data["generated_digests"])
            self.assertIn("generated/bundle/b.bin", stamp_data["generated_digests"])

            # Delete one file in the directory (partial deletion)
            _SUCCESSFUL_MATERIALIZATIONS.clear()
            (root / "generated" / "bundle" / "b.bin").unlink()
            self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_persistent_stamp_invalidated_by_git_head_advance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

            stamp_data = json.loads((root / STAMP_FILE).read_text(encoding="utf-8"))
            git_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
            self.assertEqual(git_proc.stdout.strip().lower(), stamp_data["git_revision"])

            # Commit advance in the provider repository
            subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "advance"], cwd=root, check=True)
            _SUCCESSFUL_MATERIALIZATIONS.clear()

            # Stamp is bound to previous git HEAD, so is_publication_materialized fails
            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

    def test_v3_materializer_hashes_all_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            catalog = {
                "schema_version": 3,
                "documents": [{"id": "overview", "source": "README.md", "optional": False, "home": True}],
                "assets": [{"source": "dist/output.bin", "destination": "runtime/output.bin", "optional": False}],
            }
            path = root / "docs" / "publication-catalog.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(catalog), encoding="utf-8")

            mat = root / "scripts" / "materialize_publication.py"
            mat.parent.mkdir(parents=True, exist_ok=True)
            mat.write_text(
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "out = args.source_root / 'dist' / 'output.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes(b'v3-materialized-bytes')\n",
                encoding="utf-8",
            )

            self.assertTrue(materialize_publication(root, "fixture"))
            stamp_data = json.loads((root / STAMP_FILE).read_text(encoding="utf-8"))
            self.assertIn("dist/output.bin", stamp_data["generated_digests"])

            # Tampering with dist/output.bin invalidates stamp
            (root / "dist" / "output.bin").write_bytes(b"tampered")
            self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_v4_absent_optional_generated_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            catalog = {
                "schema_version": 4,
                "documents": [{"id": "overview", "source": "README.md", "optional": False, "home": True}],
                "assets": [
                    {"source": "generated/required.bin", "destination": "runtime/required.bin", "optional": False, "source_kind": "generated"},
                    {"source": "generated/optional.bin", "destination": "runtime/optional.bin", "optional": True, "source_kind": "generated"},
                ],
            }
            path = root / "docs" / "publication-catalog.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(catalog), encoding="utf-8")

            mat = root / "scripts" / "materialize_publication.py"
            mat.parent.mkdir(parents=True, exist_ok=True)
            mat.write_text(
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "out = args.source_root / 'generated' / 'required.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes(b'required-bytes')\n",
                encoding="utf-8",
            )

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))
            stamp_data = json.loads((root / STAMP_FILE).read_text(encoding="utf-8"))
            self.assertIn("generated/required.bin", stamp_data["generated_digests"])
            self.assertNotIn("generated/optional.bin", stamp_data["generated_digests"])

    def test_memory_cache_validates_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("1", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

            # Tamper with generated asset without clearing _SUCCESSFUL_MATERIALIZATIONS
            (root / "generated" / "output.bin").write_bytes(b"tampered")
            # Next call must detect the invalid stamp and re-run materializer
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual("2", (root / "materializer-runs.txt").read_text(encoding="utf-8"))

    def test_reserved_stamp_path_collision_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            catalog = {
                "schema_version": 4,
                "documents": [{"id": "overview", "source": "README.md", "optional": False, "home": True}],
                "assets": [
                    {"source": ".publication-materialization-stamp.json", "destination": "runtime/stamp.json", "optional": False, "source_kind": "generated"}
                ],
            }
            path = root / "docs" / "publication-catalog.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(catalog), encoding="utf-8")
            self.write_materializer(root)

            with self.assertRaises(PublicationMaterializationError):
                materialize_publication(root, "fixture")

    def test_git_identity_supports_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            try:
                subprocess.run(["git", "init", "-q", "--object-format=sha256"], cwd=root, check=True)
            except subprocess.CalledProcessError:
                self.skipTest("git sha256 object format not supported by local git")
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)

            self.assertTrue(materialize_publication(root, "fixture"))
            stamp_data = json.loads((root / STAMP_FILE).read_text(encoding="utf-8"))
            self.assertEqual(64, len(stamp_data["git_revision"]))
            self.assertTrue(is_publication_materialized(root, "fixture"))

            # Advance HEAD
            subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "advance"], cwd=root, check=True)
            self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_preexisting_non_stamp_file_at_stamp_path_raises(self) -> None:
        """Finding 1: A provider-owned file at the stamp path is not silently deleted."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_catalog(root, version=4, source_kind="generated")
            self.write_materializer(root)
            # Place an unrecognized (non-stamp) file at the reserved stamp path.
            stamp_path = root / STAMP_FILE
            stamp_path.write_text(
                json.dumps({"some": "provider data", "stamp_version": "not-an-int"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "is not a materialization stamp",
            ):
                materialize_publication(root, "fixture")
            # The provider-owned file must still be on disk.
            self.assertTrue(stamp_path.exists())

    def test_v4_no_generated_assets_with_symlink_materializer_reports_not_materialized(
        self,
    ) -> None:
        """Finding 4: is_publication_materialized returns False when the materializer path
        exists but is a symlink, even for a v4 catalog with no generated assets."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Build a v4 catalog with no generated assets (source_kind=static).
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            static_asset = root / "static.bin"
            static_asset.write_bytes(b"static")
            catalog = {
                "schema_version": 4,
                "documents": [
                    {"id": "overview", "source": "README.md", "optional": False, "home": True}
                ],
                "assets": [
                    {
                        "source": "static.bin",
                        "destination": "runtime/static.bin",
                        "optional": False,
                        "source_kind": "static",
                    }
                ],
            }
            catalog_path = root / "docs" / "publication-catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            # Place a symlink at the materializer path.
            materializer_dir = root / "scripts"
            materializer_dir.mkdir(parents=True, exist_ok=True)
            symlink_target = root / "dummy_target.py"
            symlink_target.write_text("", encoding="utf-8")
            (materializer_dir / "materialize_publication.py").symlink_to(symlink_target)

            self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_v3_stamp_binds_document_and_glossary_bytes(self) -> None:
        """Finding 3: For v3 providers, document and glossary file bytes are hashed into
        the stamp so tampering with either invalidates it."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Build a v3 catalog with a document and glossary (.yml required by contract).
            doc_path = root / "README.md"
            doc_path.write_text("# Original\n", encoding="utf-8")
            glossary_path = root / "glossary.yml"
            glossary_path.write_text("entries: []\n", encoding="utf-8")
            catalog = {
                "schema_version": 3,
                "documents": [
                    {"id": "overview", "source": "README.md", "optional": False, "home": True}
                ],
                "assets": [
                    {"source": "generated/output.bin", "destination": "runtime/output.bin", "optional": False}
                ],
                "glossary": {"source": "glossary.yml"},
            }
            catalog_dir = root / "docs"
            catalog_dir.mkdir(parents=True, exist_ok=True)
            (catalog_dir / "publication-catalog.json").write_text(
                json.dumps(catalog), encoding="utf-8"
            )
            # Write a v3-style materializer that creates the generated asset.
            scripts_dir = root / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            (scripts_dir / "materialize_publication.py").write_text(
                "import argparse; from pathlib import Path; "
                "p = argparse.ArgumentParser(); p.add_argument('--source-root', type=Path); "
                "a = p.parse_args(); "
                "out = a.source_root / 'generated' / 'output.bin'; "
                "out.parent.mkdir(parents=True, exist_ok=True); "
                "out.write_bytes(b'v3 output')\n",
                encoding="utf-8",
            )

            self.assertTrue(materialize_publication(root, "fixture"))
            stamp_data = json.loads((root / STAMP_FILE).read_text(encoding="utf-8"))
            self.assertIn("README.md", stamp_data["generated_digests"])
            self.assertIn("glossary.yml", stamp_data["generated_digests"])
            self.assertTrue(is_publication_materialized(root, "fixture"))

            # Tamper with the document — stamp must be invalidated.
            doc_path.write_text("# Tampered\n", encoding="utf-8")
            self.assertFalse(is_publication_materialized(root, "fixture"))

            # Re-materialize with the tampered document to create a new valid stamp.
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

            # Now tamper with the glossary — stamp must also be invalidated.
            glossary_path.write_text("entries: [tampered: true]\n", encoding="utf-8")
            self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_git_head_change_during_materialization_raises(self) -> None:
        """Finding 2: Provider Git HEAD advancing while the materializer runs raises an error."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            try:
                subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            except subprocess.CalledProcessError:
                self.skipTest("git not available")
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)

            self.write_catalog(root, version=4, source_kind="generated")
            # Create a materializer that advances HEAD mid-run.
            path = root / "scripts" / "materialize_publication.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "import argparse, subprocess, sys\n"
                "from pathlib import Path\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--source-root', type=Path)\n"
                "a = p.parse_args()\n"
                "out = a.source_root / 'generated' / 'output.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes(b'output')\n"
                "subprocess.run(['git', 'commit', '-q', '--allow-empty', '-m', 'advance'], "
                "cwd=a.source_root, check=True)\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)

            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "provider Git HEAD changed while the materializer was running",
            ):
                materialize_publication(root, "fixture")


if __name__ == "__main__":
    unittest.main()
