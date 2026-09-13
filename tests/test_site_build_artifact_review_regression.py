"""Regression coverage for Codex P2 on later non-producing label runs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import site_build_artifact as artifact


def expected_inputs():
    return artifact.identity(
        repository='TakashiSasaki/templates',
        site='a' * 40,
        composition='b' * 40,
        policy='c' * 40,
        workflow=b'workflow',
        runtime='python|runner',
    )


def canonical_run(run_id: int, run_number: int, *, status: str = 'completed') -> dict:
    return {
        'id': run_id,
        'path': artifact.WORKFLOW,
        'head_sha': 'a' * 40,
        'event': 'pull_request',
        'head_repository': {'full_name': 'TakashiSasaki/templates'},
        'pull_requests': [{'number': 1}],
        'run_number': run_number,
        'run_attempt': 1,
        'status': status,
    }


class LaterUnrelatedLabelRunTests(unittest.TestCase):
    @patch.object(artifact, 'validate_and_extract')
    @patch.object(artifact.subprocess, 'run')
    @patch.object(artifact, 'list_all')
    def test_waiting_consumer_skips_newer_skipped_build_and_reuses_older_success(
        self, listing, download, validate
    ):
        older = canonical_run(42, 10)
        newer = canonical_run(43, 11)
        successful_build = {
            'name': 'build',
            'status': 'completed',
            'conclusion': 'success',
            'started_at': '2026-09-13T12:00:00Z',
            'completed_at': '2026-09-13T12:03:00Z',
        }
        skipped_build = dict(successful_build, conclusion='skipped')
        pages = {
            'id': 12,
            'name': 'github-pages',
            'expired': False,
            'digest': 'sha256:' + 'd' * 64,
            'workflow_run': {'id': 42, 'head_sha': 'a' * 40},
            'created_at': '2026-09-13T12:02:59Z',
        }
        listing.side_effect = [
            [older, newer],
            [skipped_build],
            [successful_build],
            [pages],
        ]

        with tempfile.TemporaryDirectory() as temporary:
            result = artifact.reuse(
                expected_inputs(),
                Path(temporary) / 'site',
                pr=1,
                current_run=99,
                timeout=0,
                wait=True,
            )

        self.assertEqual(result['producer_run'], 42)
        self.assertEqual(result['artifact_id'], 12)
        download.assert_called_once()
        validate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
