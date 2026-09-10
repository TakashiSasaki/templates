from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.materialize_publication_assets as materialization
from scripts.materialize_publication_assets import (
    STAMP_FILE,
    PublicationMaterializationError,
    is_publication_materialized,
    materialize_publication,
)


class PublicationMaterializationReviewFollowupTests(unittest.TestCase):
    def write_v4_provider(self, root: Path) -> Path:
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
                    "source": "generated/output.bin",
                    "destination": "runtime/output.bin",
                    "optional": False,
                    "source_kind": "generated",
                }
            ],
        }
        catalog_path = root / "docs" / "publication-catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

        materializer = root / "scripts" / "materialize_publication.py"
        materializer.parent.mkdir(parents=True, exist_ok=True)
        materializer.write_text(
            "from __future__ import annotations\n"
            "import argparse\n"
            "from pathlib import Path\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--source-root', type=Path, required=True)\n"
            "args = parser.parse_args()\n"
            "out = args.source_root / 'generated' / 'output.bin'\n"
            "out.parent.mkdir(parents=True, exist_ok=True)\n"
            "out.write_bytes(b'deterministic-output')\n",
            encoding="utf-8",
        )
        return materializer

    def initialize_git_checkout(self, root: Path) -> str:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=root, check=True)
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip().lower()

    def test_reserved_stamp_symlink_is_preserved_and_rejected(self) -> None:
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_v4_provider(root)
                target = root / "provider-owned-stamp-target.json"
                if not dangling:
                    target.write_text('{"provider": true}\n', encoding="utf-8")
                stamp = root / STAMP_FILE
                stamp.symlink_to(target)

                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "symbolic link",
                ):
                    materialize_publication(root, "fixture")

                self.assertTrue(stamp.is_symlink())
                if not dangling:
                    self.assertEqual(
                        '{"provider": true}\n',
                        target.read_text(encoding="utf-8"),
                    )

    def test_v4_generated_materializer_symlink_invalidates_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

            real_materializer = root / "scripts" / "real_materializer.py"
            materializer.replace(real_materializer)
            materializer.symlink_to(real_materializer)

            self.assertTrue(materializer.is_symlink())
            self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_boolean_stamp_version_does_not_establish_stamp_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            stamp = root / STAMP_FILE
            original = '{"stamp_version": true, "provider": "owned"}\n'
            stamp.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "is not a materialization stamp",
            ):
                materialize_publication(root, "fixture")

            self.assertEqual(original, stamp.read_text(encoding="utf-8"))

    def test_incomplete_integer_v1_stamp_does_not_establish_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            stamp = root / STAMP_FILE
            original = '{"stamp_version": 1, "provider": "owned"}\n'
            stamp.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "is not a materialization stamp",
            ):
                materialize_publication(root, "fixture")

            self.assertEqual(original, stamp.read_text(encoding="utf-8"))

    def test_git_identity_is_rechecked_at_stamp_commit_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            revision_a = "a" * 40
            revision_b = "b" * 40

            with patch.object(
                materialization,
                "_provider_git_untracked_paths",
                return_value=(),
            ), patch.object(
                materialization,
                "_provider_git_worktree_fingerprint",
                return_value="c" * 64,
            ), patch.object(
                materialization,
                "_provider_git_identity",
                side_effect=[revision_a, revision_a, revision_b],
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "before materialization stamp commit",
                ):
                    materialize_publication(root, "fixture")

            self.assertFalse((root / STAMP_FILE).exists())

    def test_git_identity_is_rechecked_before_success_returns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            revision_a = "a" * 40
            revision_b = "b" * 40

            with patch.object(
                materialization,
                "_provider_git_untracked_paths",
                return_value=(),
            ), patch.object(
                materialization,
                "_provider_git_worktree_fingerprint",
                return_value="c" * 64,
            ), patch.object(
                materialization,
                "_provider_git_identity",
                side_effect=[revision_a] * 7 + [revision_b],
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "before returning materialization success",
                ):
                    materialize_publication(root, "fixture")

            # The stamp may have been atomically published, but it is bound to A;
            # validation under B will reject it and the current call must not claim success.
            self.assertTrue((root / STAMP_FILE).is_file())

    def test_non_git_stamp_is_not_reused_after_process_cache_is_lost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue((root / STAMP_FILE).is_file())
            self.assertTrue(is_publication_materialized(root, "fixture"))

            # A fresh process has no in-memory success record. Simulate that boundary
            # while leaving the on-disk stamp and generated bytes untouched.
            materialization._SUCCESSFUL_MATERIALIZATIONS.clear()
            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))

    def test_enclosing_git_repository_is_not_provider_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=outer, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=outer, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=outer,
                check=True,
            )
            root = outer / "provider"
            root.mkdir()
            self.write_v4_provider(root)
            ancillary = root / "generator-input.txt"
            ancillary.write_text("revision-a\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=outer, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "outer"], cwd=outer, check=True)

            self.assertEqual("", materialization._provider_git_identity(root))
            self.assertTrue(materialize_publication(root, "fixture"))
            materialization._SUCCESSFUL_MATERIALIZATIONS.clear()

            # The enclosing repository HEAD is unchanged, but it must not authorize
            # cross-process stamp reuse for this nested non-repository provider root.
            ancillary.write_text("revision-b\n", encoding="utf-8")
            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))

    def test_git_identity_is_rechecked_before_stamp_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            revision = self.initialize_git_checkout(root)
            self.assertTrue(materialize_publication(root, "fixture"))

            advanced = "b" * len(revision)
            with patch.object(
                materialization,
                "_provider_git_identity",
                side_effect=[revision, advanced],
            ):
                self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_git_stamp_reuse_is_bound_to_dirty_worktree_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            primary = root / "generator-input.txt"
            primary.write_text("A", encoding="utf-8")
            materializer.write_text(
                "from __future__ import annotations\n"
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "primary = (args.source_root / 'generator-input.txt').read_text(encoding='utf-8')\n"
                "secondary_path = args.source_root / 'untracked-input.txt'\n"
                "secondary = secondary_path.read_text(encoding='utf-8') if secondary_path.exists() else ''\n"
                "out = args.source_root / 'generated' / 'output.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes((primary + secondary).encode('utf-8'))\n",
                encoding="utf-8",
            )
            revision = self.initialize_git_checkout(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(b"A", (root / "generated" / "output.bin").read_bytes())
            materialization._SUCCESSFUL_MATERIALIZATIONS.clear()

            # A tracked dirty input changes without advancing HEAD. Persistent reuse
            # must fail and rematerialization must observe the new bytes.
            primary.write_text("B", encoding="utf-8")
            self.assertEqual(
                revision,
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip().lower(),
            )
            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(b"B", (root / "generated" / "output.bin").read_bytes())
            materialization._SUCCESSFUL_MATERIALIZATIONS.clear()

            # An ordinary untracked generator input must also invalidate the stamp
            # while the exact Git HEAD remains unchanged.
            (root / "untracked-input.txt").write_text("C", encoding="utf-8")
            self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertEqual(b"BC", (root / "generated" / "output.bin").read_bytes())

    def test_stamp_asset_enumeration_failure_aborts_materialization(self) -> None:
        for version in (3, 4):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_v4_provider(root)
                if version == 3:
                    catalog_path = root / "docs" / "publication-catalog.json"
                    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                    catalog["schema_version"] = 3
                    for asset in catalog["assets"]:
                        asset.pop("source_kind", None)
                    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

                with patch.object(
                    materialization,
                    "asset_files",
                    side_effect=RuntimeError("forced enumeration failure"),
                ):
                    with self.assertRaisesRegex(
                        PublicationMaterializationError,
                        "unable to enumerate materialized files for stamp",
                    ):
                        materialize_publication(root, "fixture")

                self.assertFalse((root / STAMP_FILE).exists())

    def test_reserved_stamp_destination_is_not_a_provider_source_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            (root / "tracked.bin").write_bytes(b"tracked")
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
                        "source": "tracked.bin",
                        "destination": STAMP_FILE.as_posix(),
                        "optional": False,
                        "source_kind": "tracked",
                    }
                ],
            }
            catalog_path = root / "docs" / "publication-catalog.json"
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

            self.assertTrue(is_publication_materialized(root, "fixture"))
            self.assertFalse(materialize_publication(root, "fixture"))


    def test_materializer_run_is_bound_to_pre_run_tracked_and_untracked_inputs(self) -> None:
        for tracked in (True, False):
            with self.subTest(tracked=tracked), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                subprocess.run(["git", "init", "-q"], cwd=root, check=True)
                subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
                subprocess.run(
                    ["git", "config", "user.email", "test@example.com"],
                    cwd=root,
                    check=True,
                )
                materializer = self.write_v4_provider(root)
                materializer.write_text(
                    "from __future__ import annotations\n"
                    "import argparse\n"
                    "from pathlib import Path\n"
                    "parser = argparse.ArgumentParser()\n"
                    "parser.add_argument('--source-root', type=Path, required=True)\n"
                    "args = parser.parse_args()\n"
                    "source = args.source_root / 'generator-input.txt'\n"
                    "payload = source.read_bytes()\n"
                    "out = args.source_root / 'generated' / 'output.bin'\n"
                    "out.parent.mkdir(parents=True, exist_ok=True)\n"
                    "out.write_bytes(payload)\n"
                    "source.write_bytes(b'revision-b')\n",
                    encoding="utf-8",
                )
                source = root / "generator-input.txt"
                if tracked:
                    source.write_bytes(b"revision-a")
                subprocess.run(["git", "add", "."], cwd=root, check=True)
                subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=root, check=True)
                if not tracked:
                    source.write_bytes(b"revision-a")

                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "worktree changed while the materializer was running",
                ):
                    materialize_publication(root, "fixture")

                self.assertEqual(b"revision-a", (root / "generated" / "output.bin").read_bytes())
                self.assertEqual(b"revision-b", source.read_bytes())
                self.assertFalse((root / STAMP_FILE).exists())

    def test_materializer_may_create_new_generated_byproduct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            materializer.write_text(
                "from __future__ import annotations\n"
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "out = args.source_root / 'generated' / 'output.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes(b'deterministic-output')\n"
                "(args.source_root / 'generated' / 'provider-manifest.json').write_text('{}', encoding='utf-8')\n",
                encoding="utf-8",
            )
            self.initialize_git_checkout(root)

            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue((root / "generated" / "provider-manifest.json").is_file())
            self.assertTrue(is_publication_materialized(root, "fixture"))

    def test_stamp_hash_fails_if_enumerated_output_vanishes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            original = materialization._enumerate_stamp_asset_files

            def enumerate_then_remove(source_root: Path, source: str, field: str) -> list[Path]:
                files = original(source_root, source, field)
                self.assertTrue(files)
                files[0].unlink()
                return files

            with patch.object(
                materialization,
                "_enumerate_stamp_asset_files",
                side_effect=enumerate_then_remove,
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "no longer a regular non-symlink file",
                ):
                    materialize_publication(root, "fixture")

            self.assertFalse((root / STAMP_FILE).exists())


    def test_output_snapshot_is_rechecked_before_stamp_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            (root / ".gitignore").write_text("generated/\n", encoding="utf-8")
            self.initialize_git_checkout(root)
            original = materialization._snapshot_materialized_outputs
            snapshots = 0

            def mutate_after_first_snapshot(*args, **kwargs):
                nonlocal snapshots
                observed = original(*args, **kwargs)
                snapshots += 1
                if snapshots == 1:
                    (root / "generated" / "output.bin").write_bytes(b"late-mutation")
                return observed

            with patch.object(
                materialization,
                "_snapshot_materialized_outputs",
                side_effect=mutate_after_first_snapshot,
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "output snapshot changed before materialization stamp commit",
                ):
                    materialize_publication(root, "fixture")
            self.assertGreaterEqual(snapshots, 2)
            self.assertFalse((root / STAMP_FILE).exists())

    def test_ignored_output_snapshot_is_rechecked_before_stamp_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            (root / ".gitignore").write_text("generated/\n", encoding="utf-8")
            self.initialize_git_checkout(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            original = materialization._assert_provider_reuse_identity
            mutated = False

            def mutate_at_acceptance(*args, **kwargs):
                nonlocal mutated
                original(*args, **kwargs)
                if kwargs.get("boundary") == "while validating materialization stamp" and not mutated:
                    (root / "generated" / "output.bin").write_bytes(b"late-mutation")
                    mutated = True

            with patch.object(
                materialization,
                "_assert_provider_reuse_identity",
                side_effect=mutate_at_acceptance,
            ):
                self.assertFalse(is_publication_materialized(root, "fixture"))

    def test_materialization_fingerprint_is_recaptured_with_pre_run_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            self.initialize_git_checkout(root)
            replacement = materializer.read_text(encoding="utf-8").replace(
                "deterministic-output",
                "replacement-output",
            )

            def invalidate_old_stamp(*args, **kwargs):
                materializer.write_text(replacement, encoding="utf-8")
                return None

            with patch.object(
                materialization,
                "_validate_stamp",
                side_effect=invalidate_old_stamp,
            ):
                self.assertTrue(materialize_publication(root, "fixture"))

            self.assertEqual(b"replacement-output", (root / "generated" / "output.bin").read_bytes())
            self.assertTrue(is_publication_materialized(root, "fixture"))

    def test_v3_required_document_disappearance_aborts_stamping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            catalog_path = root / "docs" / "publication-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["schema_version"] = 3
            for asset in catalog["assets"]:
                asset.pop("source_kind", None)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            original = materialization._check_reserved_stamp_collision
            removed = False

            def remove_required_document(parsed_catalog, label):
                nonlocal removed
                original(parsed_catalog, label)
                if not removed:
                    (root / "README.md").unlink()
                    removed = True

            with patch.object(
                materialization,
                "_check_reserved_stamp_collision",
                side_effect=remove_required_document,
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "document README.md.*no longer a regular non-symlink file",
                ):
                    materialize_publication(root, "fixture")
            self.assertFalse((root / STAMP_FILE).exists())


    def test_new_untracked_source_path_during_materialization_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            materializer.write_text(
                "from __future__ import annotations\n"
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "out = args.source_root / 'generated' / 'output.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes(b'deterministic-output')\n"
                "(args.source_root / 'late-source.txt').write_text('late', encoding='utf-8')\n",
                encoding="utf-8",
            )
            self.initialize_git_checkout(root)
            with self.assertRaisesRegex(PublicationMaterializationError, "worktree changed while the materializer was running"):
                materialize_publication(root, "fixture")
            self.assertTrue((root / "late-source.txt").is_file())
            self.assertFalse((root / STAMP_FILE).exists())

    def test_inputs_are_rechecked_after_final_output_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            self.initialize_git_checkout(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            original = materialization._snapshot_materialized_outputs
            mutated = False
            def mutate_input_after_snapshot(*args, **kwargs):
                nonlocal mutated
                observed = original(*args, **kwargs)
                if not mutated:
                    materializer.write_text(materializer.read_text(encoding="utf-8") + "\n# late input mutation\n", encoding="utf-8")
                    mutated = True
                return observed
            with patch.object(materialization, "_snapshot_materialized_outputs", side_effect=mutate_input_after_snapshot):
                self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(mutated)

    def test_stamp_commit_preserves_path_created_by_materializer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            materializer.write_text(
                "from __future__ import annotations\n"
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "out = args.source_root / 'generated' / 'output.bin'\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_bytes(b'deterministic-output')\n"
                "stamp = args.source_root / '.publication-materialization-stamp.json'\n"
                "stamp.write_text('{\\\"provider\\\": \\\"owned\\\"}\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            self.initialize_git_checkout(root)
            with self.assertRaisesRegex(PublicationMaterializationError, "appeared before materialization stamp commit"):
                materialize_publication(root, "fixture")
            self.assertEqual('{"provider": "owned"}\n', (root / STAMP_FILE).read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
