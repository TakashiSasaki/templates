from __future__ import annotations

import json
import unittest

from scripts.report_composition_unittest_timing import (
    ReportError,
    TIMING_PREFIX,
    parse_job_log,
)


class CompositionUnittestTimingNonfiniteTests(unittest.TestCase):
    def test_nonfinite_duration_values_fail_closed(self) -> None:
        for duration in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(duration=duration):
                payload = {
                    "schema_version": 1,
                    "suite": "core",
                    "shard_count": 2,
                    "shard_index": 0,
                    "test_id": "test_nonfinite.Example.test_case",
                    "duration_seconds": duration,
                }
                log = "\n".join(
                    [
                        "2026-08-29T00:00:00Z Running core shard 1/2: 1 unittest instances",
                        "2026-08-29T00:00:01Z "
                        + TIMING_PREFIX
                        + json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    ]
                )

                with self.assertRaisesRegex(ReportError, "contains an invalid duration"):
                    parse_job_log(log, job_id=9001, job_name="core tests (1/2)")


if __name__ == "__main__":
    unittest.main()
