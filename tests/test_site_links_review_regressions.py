from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_site_links.py"


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.site_root = self.root / "site"
        self.site_root.mkdir()
        self.config_file = self.root / "zensical.toml"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.site_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--site-root",
                str(self.site_root),
                "--config-file",
                str(self.config_file),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_allows_external_mixed_unicode_non_std3_hostname(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://example.test/docs/"\n',
            encoding="utf-8",
        )
        self.write("index.html", '<a href="https://é_test.example/path">External</a>')

        result = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 0 local links across 1 generated HTML pages", result.stdout)

    def test_preserves_escaped_query_delimiter_in_configured_base_path(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://example.test/do%3Fcs/"\n',
            encoding="utf-8",
        )
        self.write("index.html", '<a href="present/">Present</a>')
        self.write("present/index.html", "<p>Present</p>")

        result = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 local links across 2 generated HTML pages", result.stdout)


if __name__ == "__main__":
    unittest.main()
