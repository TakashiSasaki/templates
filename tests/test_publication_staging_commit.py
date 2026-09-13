"""Fault-injection coverage for staging's two-file commit boundary."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.materialize_publication_staging import PublicationStagingError, materialize_many
from tests.test_publication_staging import _copy_inputs, COMPOSITION_STAGING_IDS


class StagingCommitTests(unittest.TestCase):
    def test_second_replace_failure_restores_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _copy_inputs(root)
            before = {name: (root / name).read_bytes() for name in
                      ("site-manifest.json", "reader-navigation-locales.json")}
            real_replace = os.replace

            def fail_locale(source, target):
                if Path(target).name == "reader-navigation-locales.json":
                    raise OSError("injected locale replace failure")
                return real_replace(source, target)

            with mock.patch("scripts.materialize_publication_staging.os.replace", side_effect=fail_locale):
                with self.assertRaisesRegex(OSError, "injected"):
                    materialize_many(root, list(COMPOSITION_STAGING_IDS))
            self.assertEqual(before, {name: (root / name).read_bytes() for name in before})
            self.assertEqual(list(root.glob(".*.tmp")), [])

    def test_locale_change_after_manifest_replace_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _copy_inputs(root)
            manifest_path = root / "site-manifest.json"
            locales_path = root / "reader-navigation-locales.json"
            original_manifest = manifest_path.read_bytes()
            original_locales = locales_path.read_bytes()
            concurrent_locales = original_locales + b" "
            real_replace = os.replace
            injected = False

            def inject_locale_writer(source, target):
                nonlocal injected
                result = real_replace(source, target)
                if not injected and Path(target).name == "site-manifest.json":
                    injected = True
                    locales_path.write_bytes(concurrent_locales)
                return result

            with mock.patch(
                "scripts.materialize_publication_staging.os.replace",
                side_effect=inject_locale_writer,
            ):
                with self.assertRaisesRegex(
                    PublicationStagingError,
                    "reader navigation locale overlay changed during staging",
                ):
                    materialize_many(root, list(COMPOSITION_STAGING_IDS))

            self.assertEqual(original_manifest, manifest_path.read_bytes())
            self.assertEqual(concurrent_locales, locales_path.read_bytes())
            self.assertEqual(list(root.glob(".*.tmp")), [])
