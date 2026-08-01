#!/usr/bin/env python3
"""Regression tests for deterministic Pages build provenance."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "write_build_provenance.py"
SITE_COMMIT = "a" * 40
SOURCE_COMMIT = "b" * 40


class BuildProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.output_directory = self.root / "site"
        self.output_directory.mkdir()
        self.output = self.output_directory / "build-provenance.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_writer(
        self,
        *,
        repository: str = "TakashiSasaki/templates",
        site_commit: str = SITE_COMMIT,
        source_commit: str = SOURCE_COMMIT,
        output: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(output or self.output),
                "--repository",
                repository,
                "--site-commit",
                site_commit,
                "--canonical-source-commit",
                source_commit,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_writes_deterministic_schema(self) -> None:
        first = self.run_writer()
        self.assertEqual(first.returncode, 0, first.stderr)
        first_bytes = self.output.read_bytes()

        second = self.run_writer()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.output.read_bytes(), first_bytes)
        self.assertEqual(
            json.loads(first_bytes),
            {
                "schema_version": 1,
                "repository": "TakashiSasaki/templates",
                "site_commit": SITE_COMMIT,
                "canonical_source_commit": SOURCE_COMMIT,
            },
        )

    def test_rejects_non_full_or_non_lowercase_commits(self) -> None:
        for value in ("a" * 39, "A" * 40, "g" * 40):
            with self.subTest(value=value):
                result = self.run_writer(site_commit=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "site commit must be a full lowercase 40-character Git commit SHA",
                    result.stderr,
                )

    def test_rejects_invalid_repository_identifier(self) -> None:
        result = self.run_writer(repository="TakashiSasaki")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("repository must be an owner/name identifier", result.stderr)

    def test_rejects_missing_output_directory(self) -> None:
        result = self.run_writer(output=self.root / "missing" / "provenance.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("output directory does not exist", result.stderr)

    def test_rejects_symbolic_link_output(self) -> None:
        target = self.output_directory / "target.json"
        target.write_text("{}\n", encoding="utf-8")
        self.output.symlink_to(target)

        result = self.run_writer()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("output path must not be a symbolic link", result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "{}\n")


if __name__ == "__main__":
    unittest.main()
