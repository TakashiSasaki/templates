from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import call, patch
from urllib.error import HTTPError

from scripts.prepare_chromedriver import (
    ARCHIVE_MEMBER,
    ChromeDriverPreparationError,
    download_bytes,
    driver_archive_url,
    latest_release_url,
    parse_four_part_version,
    resolve_driver_archive,
    resolve_driver_version,
    version_build,
    write_driver_from_zip,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


class PrepareChromeDriverTests(unittest.TestCase):
    def test_version_helpers_preserve_exact_patch_and_build_fallback(self) -> None:
        chrome = parse_four_part_version("Google Chrome 151.0.7922.173")
        self.assertEqual(chrome, "151.0.7922.173")
        self.assertEqual(version_build(chrome), "151.0.7922")
        self.assertEqual(
            latest_release_url(chrome),
            "https://googlechromelabs.github.io/chrome-for-testing/"
            "LATEST_RELEASE_151.0.7922",
        )
        self.assertEqual(
            driver_archive_url(chrome),
            "https://storage.googleapis.com/chrome-for-testing-public/"
            "151.0.7922.173/linux64/chromedriver-linux64.zip",
        )

    def test_exact_driver_patch_is_preferred_when_asset_exists(self) -> None:
        chrome = "151.0.7922.173"
        with patch(
            "scripts.prepare_chromedriver.download_bytes",
            return_value=b"exact-driver",
        ) as download, patch(
            "scripts.prepare_chromedriver.download_text"
        ) as release:
            version, archive = resolve_driver_archive(chrome)

        self.assertEqual(version, chrome)
        self.assertEqual(archive, b"exact-driver")
        download.assert_called_once_with(driver_archive_url(chrome), missing_ok=True)
        release.assert_not_called()

    def test_missing_exact_patch_falls_back_to_latest_same_build_driver(self) -> None:
        chrome = "151.0.7922.137"
        fallback = "151.0.7922.138"
        with patch(
            "scripts.prepare_chromedriver.download_bytes",
            side_effect=[None, b"fallback-driver"],
        ) as download, patch(
            "scripts.prepare_chromedriver.download_text",
            return_value=f"{fallback}\n",
        ) as release:
            version, archive = resolve_driver_archive(chrome)

        self.assertEqual(version, fallback)
        self.assertEqual(archive, b"fallback-driver")
        self.assertEqual(
            download.call_args_list,
            [
                call(driver_archive_url(chrome), missing_ok=True),
                call(driver_archive_url(fallback)),
            ],
        )
        release.assert_called_once_with(latest_release_url(chrome))

    def test_missing_ok_suppresses_only_http_404(self) -> None:
        url = driver_archive_url("151.0.7922.173")
        not_found = HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
        server_error = HTTPError(url, 500, "Server Error", hdrs=None, fp=None)

        with patch("scripts.prepare_chromedriver.urlopen", side_effect=not_found):
            self.assertIsNone(download_bytes(url, missing_ok=True))

        with patch("scripts.prepare_chromedriver.urlopen", side_effect=server_error):
            with self.assertRaises(ChromeDriverPreparationError):
                download_bytes(url, missing_ok=True)

    def test_driver_resolution_accepts_latest_patch_for_same_build(self) -> None:
        self.assertEqual(
            resolve_driver_version("151.0.7922.137", "151.0.7922.138\n"),
            "151.0.7922.138",
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

    def test_schema_workflow_prepares_driver_only_for_real_browser_job(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("- name: Prepare compatible ChromeDriver"), 1)
        self.assertEqual(workflow.count("scripts/prepare_chromedriver.py"), 1)
        self.assertEqual(workflow.count('echo "CHROMEWEBDRIVER=$driver_path" >> "$GITHUB_ENV"'), 1)
        self.assertEqual(workflow.count('"$CHROMEWEBDRIVER" --version'), 1)
        browser_job = workflow.split("\n  real_browser:\n", 1)[1].split("\n  validate:\n", 1)[0]
        core_jobs = workflow.split("\n  real_browser:\n", 1)[0]
        self.assertIn("Prepare compatible ChromeDriver", browser_job)
        self.assertNotIn("Prepare compatible ChromeDriver", core_jobs)
        self.assertNotIn("\n          chromedriver --version\n", workflow)


if __name__ == "__main__":
    unittest.main()
