from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_composition_unittest_timing import (
    ReportError,
    TIMING_PREFIX,
    build_report,
    write_summary,
)


class CompositionUnittestTimingReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def _record(test_id: str, duration: float, shard_index: int, **updates: object) -> str:
        payload: dict[str, object] = {
            "schema_version": 1,
            "suite": "core",
            "shard_count": 2,
            "shard_index": shard_index,
            "test_id": test_id,
            "duration_seconds": duration,
        }
        payload.update(updates)
        return TIMING_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _write_log(
        self,
        run_id: int,
        job_id: int,
        *,
        shard_index: int,
        records: list[str],
        expected_count: int | None = None,
        region: str = "eastus",
    ) -> str:
        run_dir = self.root / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        count = len(records) if expected_count is None else expected_count
        lines = [
            "2026-08-29T00:00:00Z Hosted Compute Agent",
            f"2026-08-29T00:00:00Z Azure Region: {region}",
            f"2026-08-29T00:00:01Z Running core shard {shard_index + 1}/2: {count} unittest instances",
            *[f"2026-08-29T00:00:02Z {record}" for record in records],
        ]
        relative = f"{run_id}/{job_id}.log"
        (self.root / relative).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return relative

    def _write_legacy_log(self, run_id: int, job_id: int) -> str:
        run_dir = self.root / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        relative = f"{run_id}/{job_id}.log"
        (self.root / relative).write_text(
            "2026-08-28T00:00:00Z Ran 376 tests in 100.000s\n",
            encoding="utf-8",
        )
        return relative

    def _manifest_run(
        self,
        run_id: int,
        shard_zero_log: str,
        shard_one_log: str,
    ) -> dict[str, object]:
        return {
            "id": run_id,
            "head_sha": f"{run_id:040x}"[-40:],
            "run_started_at": "2026-08-29T00:00:00Z",
            "html_url": f"https://github.com/TakashiSasaki/templates/actions/runs/{run_id}",
            "jobs": [
                {
                    "id": run_id * 10,
                    "name": "core tests (1/2)",
                    "log_path": shard_zero_log,
                },
                {
                    "id": run_id * 10 + 1,
                    "name": "preflight + core tests (2/2)",
                    "log_path": shard_one_log,
                },
            ],
        }

    @staticmethod
    def _manifest(runs: list[dict[str, object]], requested_runs: int = 5) -> dict[str, object]:
        return {
            "schema_version": 1,
            "repository": "TakashiSasaki/templates",
            "workflow": "Composition schema validation",
            "branch": "composition",
            "requested_runs": requested_runs,
            "runs": runs,
        }

    def test_multiple_canonical_runs_produce_per_test_and_shard_statistics(self) -> None:
        run1_zero = self._write_log(
            101,
            1010,
            shard_index=0,
            records=[
                self._record("test_a.Example.test_a", 1.0, 0),
                self._record("test_b.Example.test_b", 2.0, 0),
            ],
            region="eastus",
        )
        run1_one = self._write_log(
            101,
            1011,
            shard_index=1,
            records=[self._record("test_c.Example.test_c", 3.0, 1)],
            region="westus",
        )
        run2_zero = self._write_log(
            102,
            1020,
            shard_index=0,
            records=[
                self._record("test_a.Example.test_a", 1.5, 0),
                self._record("test_b.Example.test_b", 2.5, 0),
            ],
            region="centralus",
        )
        run2_one = self._write_log(
            102,
            1021,
            shard_index=1,
            records=[self._record("test_c.Example.test_c", 4.0, 1)],
            region="westus",
        )

        report = build_report(
            self._manifest(
                [
                    self._manifest_run(101, run1_zero, run1_one),
                    self._manifest_run(102, run2_zero, run2_one),
                ],
                requested_runs=2,
            ),
            self.root,
        )

        self.assertEqual(report["selection"]["telemetry_runs"], 2)
        self.assertEqual(report["selection"]["legacy_runs_without_telemetry"], [])
        test_stats = {
            item["test_id"]: item for item in report["telemetry"]["test_stats"]
        }
        self.assertEqual(test_stats["test_a.Example.test_a"]["sample_count"], 2)
        self.assertEqual(test_stats["test_a.Example.test_a"]["median_seconds"], 1.25)
        self.assertEqual(test_stats["test_a.Example.test_a"]["p90_seconds"], 1.5)
        self.assertEqual(test_stats["test_c.Example.test_c"]["median_seconds"], 3.5)

        shard_stats = {
            item["shard_index"]: item for item in report["telemetry"]["shard_stats"]
        }
        self.assertEqual(shard_stats[0]["median_test_seconds"], 3.5)
        self.assertEqual(shard_stats[1]["median_test_seconds"], 3.5)
        self.assertEqual(shard_stats[0]["regions"], ["centralus", "eastus"])
        self.assertEqual(shard_stats[1]["regions"], ["westus"])

        summary = self.root / "summary.md"
        write_summary(report, summary)
        summary_text = summary.read_text(encoding="utf-8")
        self.assertIn("Canonical telemetry runs: **2** / 2", summary_text)
        self.assertIn("Do not rebalance shards from a single telemetry run", summary_text)
        self.assertIn("`test_c.Example.test_c`", summary_text)

    def test_wholly_legacy_run_is_skipped_without_failing_report(self) -> None:
        zero = self._write_legacy_log(201, 2010)
        one = self._write_legacy_log(201, 2011)
        report = build_report(
            self._manifest([self._manifest_run(201, zero, one)]),
            self.root,
        )
        self.assertEqual(report["selection"]["telemetry_runs"], 0)
        self.assertEqual(report["selection"]["legacy_runs_without_telemetry"], [201])
        self.assertEqual(report["telemetry"]["test_stats"], [])

    def test_partial_telemetry_fails_closed(self) -> None:
        zero = self._write_log(
            301,
            3010,
            shard_index=0,
            records=[self._record("test_a.Example.test_a", 1.0, 0)],
        )
        one = self._write_legacy_log(301, 3011)
        with self.assertRaisesRegex(ReportError, "partial core timing telemetry"):
            build_report(
                self._manifest([self._manifest_run(301, zero, one)]),
                self.root,
            )

    def test_record_count_mismatch_fails_closed(self) -> None:
        zero = self._write_log(
            401,
            4010,
            shard_index=0,
            expected_count=2,
            records=[self._record("test_a.Example.test_a", 1.0, 0)],
        )
        one = self._write_log(
            401,
            4011,
            shard_index=1,
            records=[self._record("test_c.Example.test_c", 3.0, 1)],
        )
        with self.assertRaisesRegex(ReportError, "expected 2 timing records but found 1"):
            build_report(
                self._manifest([self._manifest_run(401, zero, one)]),
                self.root,
            )

    def test_duplicate_test_id_across_shards_fails_closed(self) -> None:
        duplicate = "test_duplicate.Example.test_case"
        zero = self._write_log(
            501,
            5010,
            shard_index=0,
            records=[self._record(duplicate, 1.0, 0)],
        )
        one = self._write_log(
            501,
            5011,
            shard_index=1,
            records=[self._record(duplicate, 1.0, 1)],
        )
        with self.assertRaisesRegex(ReportError, "in multiple core shards"):
            build_report(
                self._manifest([self._manifest_run(501, zero, one)]),
                self.root,
            )

    def test_unknown_timing_schema_fails_closed(self) -> None:
        zero = self._write_log(
            601,
            6010,
            shard_index=0,
            records=[
                self._record(
                    "test_a.Example.test_a",
                    1.0,
                    0,
                    schema_version=2,
                )
            ],
        )
        one = self._write_log(
            601,
            6011,
            shard_index=1,
            records=[self._record("test_c.Example.test_c", 1.0, 1)],
        )
        with self.assertRaisesRegex(ReportError, "unsupported timing schema version 2"):
            build_report(
                self._manifest([self._manifest_run(601, zero, one)]),
                self.root,
            )


if __name__ == "__main__":
    unittest.main()
