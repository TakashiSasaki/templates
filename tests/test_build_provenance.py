#!/usr/bin/env python3
"""CLI regression tests for deterministic multi-publication provenance."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "write_publication_provenance.py"
)
SITE_COMMIT = "a" * 40
COMPOSITION_COMMIT = "b" * 40
POLICY_COMMIT = "c" * 40
DEPLOYMENT_TIMESTAMP = "2026-08-15 22:07:00 JST"


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
        publication_commits: tuple[str, ...] = (
            f"composition={COMPOSITION_COMMIT}",
            f"policy={POLICY_COMMIT}",
        ),
        output: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(output or self.output),
            "--repository",
            repository,
            "--site-commit",
            site_commit,
        ]
        for value in publication_commits:
            command.extend(("--publication-commit", value))
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_writes_deterministic_schema_v2(self) -> None:
        first = self.run_writer()
        self.assertEqual(first.returncode, 0, first.stderr)
        first_bytes = self.output.read_bytes()

        second = self.run_writer()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.output.read_bytes(), first_bytes)
        self.assertEqual(
            json.loads(first_bytes),
            {
                "schema_version": 2,
                "repository": "TakashiSasaki/templates",
                "site_commit": SITE_COMMIT,
                "publication_commits": {
                    "composition": COMPOSITION_COMMIT,
                    "policy": POLICY_COMMIT,
                },
            },
        )

    def test_cli_projects_freshness_identity_when_index_exists(self) -> None:
        index = self.output_directory / "index.html"
        index.write_text(
            "<html><head><title>Test</title></head>"
            f"<body>Deployment time: {DEPLOYMENT_TIMESTAMP}</body></html>",
            encoding="utf-8",
        )

        result = self.run_writer()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Wrote build provenance to", result.stdout)
        self.assertIn("Wrote freshness identity to", result.stdout)
        site_version = self.output_directory / "site-version.json"
        self.assertTrue(site_version.is_file())
        self.assertEqual(
            {
                "schema_version": 1,
                "site_revision": SITE_COMMIT,
                "deployed_at": DEPLOYMENT_TIMESTAMP,
                "publications": {
                    "composition": COMPOSITION_COMMIT,
                    "policy": POLICY_COMMIT,
                },
            },
            json.loads(site_version.read_text(encoding="utf-8")),
        )
        self.assertIn(
            f'<meta name="templates-site-revision" content="{SITE_COMMIT}">',
            index.read_text(encoding="utf-8"),
        )

    def test_rejects_non_full_or_non_lowercase_site_commit(self) -> None:
        for value in ("a" * 39, "A" * 40, "g" * 40):
            with self.subTest(value=value):
                result = self.run_writer(site_commit=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "site commit must be a full lowercase 40-character Git commit SHA",
                    result.stderr,
                )

    def test_rejects_invalid_publication_commit(self) -> None:
        result = self.run_writer(publication_commits=("composition=not-a-sha",))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "composition publication commit must be a full lowercase 40-character Git commit SHA",
            result.stderr,
        )

    def test_rejects_duplicate_publication_name(self) -> None:
        result = self.run_writer(
            publication_commits=(
                f"composition={COMPOSITION_COMMIT}",
                f"composition={POLICY_COMMIT}",
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate publication commit: composition", result.stderr)

    def test_requires_at_least_one_publication_commit(self) -> None:
        result = self.run_writer(publication_commits=())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least one publication commit is required", result.stderr)

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
