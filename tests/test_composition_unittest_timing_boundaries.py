from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_composition_unittest_timing import (
    ReportError,
    TIMING_PREFIX,
    build_report,
)


class CompositionUnittestTimingBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def _record(
        test_id: str,
        duration: object,
        shard_index: int,
    ) -> str:
        payload = {
            "schema_version": 1,
            "suite": "core",
            "shard_count": 2,
            "shard_index": shard_index,
            "test_id": test_id,
            "duration_seconds": duration,
        }
        return TIMING_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _write_log(
        self,
        run_id: int,
        job_id: int,
        *,
        shard_index: int,
        records: list[str],
        expected_count: int | None = None,
    ) -> str:
        run_dir = self.root / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        count = len(records) if expected_count is None else expected_count
        relative = f"{run_id}/{job_id}.log"
        (self.root / relative).write_text(
            "\n".join(
                [
                    "2026-08-29T00:00:00Z Hosted Compute Agent",
                    "2026-08-29T00:00:00Z Azure Region: eastus",
                    f"2026-08-29T00:00:01Z Running core shard {shard_index + 1}/2: {count} unittest instances",
                    *[
                        f"2026-08-29T00:00:02Z {record}"
                        for record in records
                    ],
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return relative

    @staticmethod
    def _manifest_run(
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
    def _manifest(runs: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "repository": "TakashiSasaki/templates",
            "workflow": "Composition schema validation",
            "branch": "composition",
            "requested_runs": 3,
            "runs": runs,
        }

    def _valid_other_shard(self, run_id: int) -> str:
        return self._write_log(
            run_id,
            run_id * 10 + 1,
            shard_index=1,
            records=[self._record("test_other.Example.test_case", 1.0, 1)],
        )

    def test_duplicate_test_id_within_shard_fails_closed(self) -> None:
        duplicate = "test_duplicate.Example.test_case"
        zero = self._write_log(
            701,
            7010,
            shard_index=0,
            records=[
                self._record(duplicate, 1.0, 0),
                self._record(duplicate, 2.0, 0),
            ],
        )
        one = self._valid_other_shard(701)

        with self.assertRaisesRegex(ReportError, "contains duplicate unittest id"):
            build_report(
                self._manifest([self._manifest_run(701, zero, one)]),
                self.root,
            )

    def test_invalid_duration_values_fail_closed(self) -> None:
        invalid_values = (-1.0, True, "1.0", None)
        for offset, value in enumerate(invalid_values):
            with self.subTest(value=value):
                run_id = 710 + offset
                zero = self._write_log(
                    run_id,
                    run_id * 10,
                    shard_index=0,
                    records=[
                        self._record(
                            f"test_invalid_{offset}.Example.test_case",
                            value,
                            0,
                        )
                    ],
                )
                one = self._valid_other_shard(run_id)
                with self.assertRaisesRegex(ReportError, "contains an invalid duration"):
                    build_report(
                        self._manifest([self._manifest_run(run_id, zero, one)]),
                        self.root,
                    )

    def test_manifest_wrong_workflow_and_branch_fail_closed(self) -> None:
        for field, value, message in (
            (
                "workflow",
                "Other workflow",
                "input manifest is not for Composition schema validation",
            ),
            (
                "branch",
                "agent/example",
                "input manifest must sample the canonical composition branch",
            ),
        ):
            with self.subTest(field=field):
                manifest = self._manifest([])
                manifest[field] = value
                with self.assertRaisesRegex(ReportError, message):
                    build_report(manifest, self.root)

    def test_unsafe_log_paths_fail_closed(self) -> None:
        for unsafe_path in ("../outside.log", "/etc/passwd"):
            with self.subTest(unsafe_path=unsafe_path):
                manifest = self._manifest(
                    [
                        self._manifest_run(
                            801,
                            unsafe_path,
                            unsafe_path,
                        )
                    ]
                )
                with self.assertRaisesRegex(ReportError, "unsafe log path in manifest"):
                    build_report(manifest, self.root)


if __name__ == "__main__":
    unittest.main()
