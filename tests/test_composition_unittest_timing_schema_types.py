from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_composition_unittest_timing import (
    ReportError,
    TIMING_PREFIX,
    build_report,
    parse_job_log,
)


class CompositionUnittestTimingSchemaTypeTests(unittest.TestCase):
    def test_boolean_timing_schema_version_is_rejected(self) -> None:
        payload = {
            "schema_version": True,
            "suite": "core",
            "shard_count": 2,
            "shard_index": 0,
            "test_id": "test_example.ExampleTests.test_case",
            "duration_seconds": 0.1,
        }
        log = "\n".join(
            [
                "Running core shard 1/2: 1 unittest instances",
                TIMING_PREFIX + json.dumps(payload, separators=(",", ":")),
            ]
        )

        with self.assertRaisesRegex(
            ReportError,
            "unsupported timing schema version True",
        ):
            parse_job_log(log, job_id=123, job_name="core tests (1/2)")

    def test_boolean_manifest_schema_version_is_rejected(self) -> None:
        manifest = {
            "schema_version": True,
            "repository": "TakashiSasaki/templates",
            "workflow": "Composition schema validation",
            "branch": "composition",
            "requested_runs": 1,
            "runs": [],
        }
        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaisesRegex(
                ReportError,
                "unsupported input manifest schema version",
            ):
                build_report(manifest, Path(tempdir))


if __name__ == "__main__":
    unittest.main()
