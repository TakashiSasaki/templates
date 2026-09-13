"""Adversarial coverage for staging's isolated snapshot boundary."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.materialize_publication_staging import (
    PublicationStagingError,
    materialize_many,
)
from tests.test_publication_staging import _copy_inputs, COMPOSITION_STAGING_IDS


class StagingSnapshotTests(unittest.TestCase):
    def test_materialization_never_replaces_source_mapping_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "site-source"
            root.mkdir()
            _copy_inputs(root)
            before = {
                name: (root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }

            staged_root = materialize_many(root, list(COMPOSITION_STAGING_IDS))

            self.assertNotEqual(root, staged_root)
            self.assertEqual(
                before,
                {
                    name: (root / name).read_bytes()
                    for name in before
                },
            )
            self.assertNotEqual(
                before["site-manifest.json"],
                (staged_root / "site-manifest.json").read_bytes(),
            )
            self.assertNotEqual(
                before["reader-navigation-locales.json"],
                (staged_root / "reader-navigation-locales.json").read_bytes(),
            )

    def test_concurrent_locale_source_change_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "site-source"
            root.mkdir()
            _copy_inputs(root)
            manifest_before = (root / "site-manifest.json").read_bytes()
            locales_path = root / "reader-navigation-locales.json"
            concurrent_locales = locales_path.read_bytes() + b" "

            from scripts import materialize_publication_staging as staging
            real_copytree = staging.shutil.copytree

            def copy_then_change_locale(*args, **kwargs):
                result = real_copytree(*args, **kwargs)
                locales_path.write_bytes(concurrent_locales)
                return result

            with mock.patch.object(staging.shutil, "copytree", side_effect=copy_then_change_locale):
                with self.assertRaisesRegex(
                    PublicationStagingError,
                    "Site mapping changed during staging",
                ):
                    materialize_many(root, list(COMPOSITION_STAGING_IDS))

            self.assertEqual(manifest_before, (root / "site-manifest.json").read_bytes())
            self.assertEqual(concurrent_locales, locales_path.read_bytes())
            self.assertEqual(
                [],
                list(Path(directory).glob(".site-source.publication-staging-*")),
            )

    def test_concurrent_manifest_source_change_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "site-source"
            root.mkdir()
            _copy_inputs(root)
            manifest_path = root / "site-manifest.json"
            concurrent_manifest = manifest_path.read_bytes() + b" "
            locales_before = (root / "reader-navigation-locales.json").read_bytes()

            from scripts import materialize_publication_staging as staging
            real_copytree = staging.shutil.copytree

            def copy_then_change_manifest(*args, **kwargs):
                result = real_copytree(*args, **kwargs)
                manifest_path.write_bytes(concurrent_manifest)
                return result

            with mock.patch.object(staging.shutil, "copytree", side_effect=copy_then_change_manifest):
                with self.assertRaisesRegex(
                    PublicationStagingError,
                    "Site mapping changed during staging",
                ):
                    materialize_many(root, list(COMPOSITION_STAGING_IDS))

            self.assertEqual(concurrent_manifest, manifest_path.read_bytes())
            self.assertEqual(
                locales_before,
                (root / "reader-navigation-locales.json").read_bytes(),
            )
            self.assertEqual(
                [],
                list(Path(directory).glob(".site-source.publication-staging-*")),
            )
