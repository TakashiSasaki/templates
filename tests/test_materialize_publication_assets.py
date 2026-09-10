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


if __name__ == "__main__":
    unittest.main()
