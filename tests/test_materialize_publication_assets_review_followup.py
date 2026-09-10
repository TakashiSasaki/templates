from __future__ import annotations

import json
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

    def test_git_identity_is_rechecked_at_stamp_commit_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_v4_provider(root)
            revision_a = "a" * 40
            revision_b = "b" * 40

            with patch.object(
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
                "_provider_git_identity",
                side_effect=[revision_a, revision_a, revision_a, revision_b],
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "before returning materialization success",
                ):
                    materialize_publication(root, "fixture")

            # The stamp may have been atomically published, but it is bound to A;
            # validation under B will reject it and the current call must not claim success.
            self.assertTrue((root / STAMP_FILE).is_file())


if __name__ == "__main__":
    unittest.main()
