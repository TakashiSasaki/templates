from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.prepare_chromedriver import (
    ARCHIVE_MEMBER,
    ChromeDriverPreparationError,
    driver_archive_url,
    latest_release_url,
    parse_four_part_version,
    resolve_driver_version,
    version_build,
    write_driver_from_zip,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


class PrepareChromeDriverTests(unittest.TestCase):
    def test_version_helpers_follow_chrome_build_selection_boundary(self) -> None:
        chrome = parse_four_part_version("Google Chrome 151.0.7922.173")
        self.assertEqual(chrome, "151.0.7922.173")
        self.assertEqual(version_build(chrome), "151.0.7922")
        self.assertEqual(
            latest_release_url(chrome),
            "https://googlechromelabs.github.io/chrome-for-testing/"
            "LATEST_RELEASE_151.0.7922",
        )
        self.assertEqual(
            driver_archive_url("151.0.7922.174"),
            "https://storage.googleapis.com/chrome-for-testing-public/"
            "151.0.7922.174/linux64/chromedriver-linux64.zip",
        )

    def test_driver_resolution_accepts_latest_patch_for_same_build(self) -> None:
        self.assertEqual(
            resolve_driver_version("151.0.7922.173", "151.0.7922.174\n"),
            "151.0.7922.174",
        )

    def test_driver_resolution_fails_closed_on_mismatched_or_invalid_version(self) -> None:
        for release in ("152.0.7977.54", "not-a-version"):
            with self.subTest(release=release):
                with self.assertRaises(ChromeDriverPreparationError):
                    resolve_driver_version("151.0.7922.173", release)
        with self.assertRaises(ChromeDriverPreparationError):
            parse_four_part_version("Google Chrome unknown")

    def test_archive_writer_extracts_only_expected_driver_member(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(ARCHIVE_MEMBER, b"driver-bytes")
            bundle.writestr("chromedriver-linux64/LICENSE.chromedriver", b"license")
            bundle.writestr("../escape", b"must-not-extract")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "bin" / "chromedriver"
            write_driver_from_zip(archive.getvalue(), destination)
            self.assertEqual(destination.read_bytes(), b"driver-bytes")
            self.assertTrue(os.access(destination, os.X_OK))
            self.assertFalse((root / "escape").exists())

    def test_archive_writer_requires_expected_nonempty_member(self) -> None:
        for member, content in (("other", b"driver"), (ARCHIVE_MEMBER, b"")):
            with self.subTest(member=member, content=content):
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr(member, content)
                with tempfile.TemporaryDirectory() as temporary:
                    with self.assertRaises(ChromeDriverPreparationError):
                        write_driver_from_zip(
                            archive.getvalue(),
                            Path(temporary) / "chromedriver",
                        )

    def test_schema_workflow_prepares_driver_for_both_test_bearing_jobs(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("- name: Prepare compatible ChromeDriver"), 2)
        self.assertEqual(workflow.count("scripts/prepare_chromedriver.py"), 2)
        self.assertEqual(workflow.count('echo "CHROMEWEBDRIVER=$driver_path" >> "$GITHUB_ENV"'), 2)
        self.assertEqual(workflow.count('"$CHROMEWEBDRIVER" --version'), 2)
        self.assertNotIn("\n          chromedriver --version\n", workflow)


if __name__ == "__main__":
    unittest.main()
