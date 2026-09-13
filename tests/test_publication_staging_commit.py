"""Fault-injection coverage for staging's two-file commit boundary."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.materialize_publication_staging import materialize_many
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
