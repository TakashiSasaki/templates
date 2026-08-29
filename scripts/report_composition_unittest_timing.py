#!/usr/bin/env python3
"""Aggregate Composition unittest timing telemetry from downloaded Actions job logs."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


TIMING_PREFIX = "COMPOSITION_UNITTEST_TIMING "
TIMING_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
CORE_JOB_NAMES = frozenset({"core tests (1/2)", "preflight + core tests (2/2)"})
TIMING_FIELDS = frozenset(
    {
        "duration_seconds",
        "schema_version",
        "shard_count",
        "shard_index",
        "suite",
        "test_id",
    }
)
RUNNING_RE = re.compile(r"Running core shard (\d+)/(\d+): (\d+) unittest instances")
REGION_RE = re.compile(r"Azure Region:\s*([^\r\n]+)")


class ReportError(ValueError):
    """Raised when telemetry input is present but violates its machine contract."""


def _numeric(values: Iterable[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def median(values: Iterable[float]) -> float | None:
    ordered = sorted(_numeric(values))
    if not ordered:
        return None
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(_numeric(values))
    if not ordered:
        return None
    index = math.ceil(probability * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _read_log(input_dir: Path, relative_path: str) -> str:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ReportError(f"unsafe log path in manifest: {relative_path}")
    root = input_dir.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReportError(f"log path escapes input directory: {relative_path}") from exc
    try:
        return resolved.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ReportError(f"could not read job log {relative_path}: {exc}") from exc


def parse_job_log(text: str, *, job_id: int, job_name: str) -> dict[str, Any] | None:
    """Parse one core job log; return None for a pre-telemetry legacy log."""
    marker_lines = [line for line in text.splitlines() if TIMING_PREFIX in line]
    if not marker_lines:
        return None

    running_matches = RUNNING_RE.findall(text)
    if len(running_matches) != 1:
        raise ReportError(
            f"job {job_id} has telemetry but expected exactly one core-shard run header; "
            f"found {len(running_matches)}"
        )
    raw_shard_number, raw_shard_count, raw_expected_count = running_matches[0]
    shard_number = int(raw_shard_number)
    shard_count = int(raw_shard_count)
    shard_index = shard_number - 1
    expected_count = int(raw_expected_count)
    if shard_count != 2 or shard_index not in {0, 1}:
        raise ReportError(
            f"job {job_id} reports unsupported core shard {shard_number}/{shard_count}"
        )

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line in marker_lines:
        payload_text = line.split(TIMING_PREFIX, 1)[1].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ReportError(f"job {job_id} contains malformed timing JSON: {exc}") from exc
        if not isinstance(payload, dict) or set(payload) != TIMING_FIELDS:
            raise ReportError(f"job {job_id} contains an unexpected timing record shape")
        if payload["schema_version"] != TIMING_SCHEMA_VERSION:
            raise ReportError(
                f"job {job_id} uses unsupported timing schema version "
                f"{payload['schema_version']!r}"
            )
        if payload["suite"] != "core":
            raise ReportError(f"job {job_id} contains non-core timing telemetry")
        if type(payload["shard_count"]) is not int or payload["shard_count"] != shard_count:
            raise ReportError(f"job {job_id} timing shard_count disagrees with run header")
        if type(payload["shard_index"]) is not int or payload["shard_index"] != shard_index:
            raise ReportError(f"job {job_id} timing shard_index disagrees with run header")
        test_id = payload["test_id"]
        if not isinstance(test_id, str) or not test_id:
            raise ReportError(f"job {job_id} contains an invalid unittest id")
        if test_id in seen_ids:
            raise ReportError(f"job {job_id} contains duplicate unittest id {test_id}")
        seen_ids.add(test_id)
        duration = payload["duration_seconds"]
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(float(duration))
            or duration < 0
        ):
            raise ReportError(f"job {job_id} contains an invalid duration for {test_id}")
        records.append(
            {
                "test_id": test_id,
                "duration_seconds": float(duration),
                "suite": "core",
                "shard_count": shard_count,
                "shard_index": shard_index,
            }
        )

    if len(records) != expected_count:
        raise ReportError(
            f"job {job_id} expected {expected_count} timing records but found {len(records)}"
        )

    region_match = REGION_RE.search(text)
    return {
        "job_id": job_id,
        "job_name": job_name,
        "region": region_match.group(1).strip() if region_match else None,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "expected_test_count": expected_count,
        "record_count": len(records),
        "records": records,
    }


def parse_run(run: dict[str, Any], input_dir: Path) -> dict[str, Any] | None:
    """Parse one successful schema run, skipping only wholly pre-telemetry runs."""
    jobs = run.get("jobs")
    if not isinstance(jobs, list):
        raise ReportError(f"run {run.get('id')} has no job manifest")

    parsed_jobs: list[dict[str, Any] | None] = []
    job_names: list[str] = []
    for job in jobs:
        if not isinstance(job, dict):
            raise ReportError(f"run {run.get('id')} contains a malformed job manifest")
        job_id = job.get("id")
        job_name = job.get("name")
        log_path = job.get("log_path")
        if type(job_id) is not int or not isinstance(job_name, str) or not isinstance(log_path, str):
            raise ReportError(f"run {run.get('id')} contains invalid job metadata")
        job_names.append(job_name)
        parsed_jobs.append(
            parse_job_log(
                _read_log(input_dir, log_path),
                job_id=job_id,
                job_name=job_name,
            )
        )

    available = [job for job in parsed_jobs if job is not None]
    if not available:
        return None
    if set(job_names) != CORE_JOB_NAMES or len(jobs) != 2:
        raise ReportError(
            f"run {run.get('id')} has telemetry but does not contain exactly the two current core jobs"
        )
    if len(available) != 2:
        raise ReportError(f"run {run.get('id')} contains partial core timing telemetry")

    shard_indexes = {job["shard_index"] for job in available}
    if shard_indexes != {0, 1}:
        raise ReportError(f"run {run.get('id')} does not cover both core shard indexes")

    seen_ids: set[str] = set()
    for job in available:
        for record in job["records"]:
            test_id = record["test_id"]
            if test_id in seen_ids:
                raise ReportError(
                    f"run {run.get('id')} contains unittest id {test_id} in multiple core shards"
                )
            seen_ids.add(test_id)

    return {
        "id": run.get("id"),
        "head_sha": run.get("head_sha"),
        "run_started_at": run.get("run_started_at"),
        "html_url": run.get("html_url"),
        "jobs": available,
    }


def build_report(manifest: dict[str, Any], input_dir: Path) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ReportError("unsupported input manifest schema version")
    if manifest.get("workflow") != "Composition schema validation":
        raise ReportError("input manifest is not for Composition schema validation")
    if manifest.get("branch") != "composition":
        raise ReportError("input manifest must sample the canonical composition branch")
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise ReportError("input manifest runs must be a list")

    telemetry_runs: list[dict[str, Any]] = []
    legacy_run_ids: list[int] = []
    for run in runs:
        if not isinstance(run, dict) or type(run.get("id")) is not int:
            raise ReportError("input manifest contains a malformed run")
        parsed = parse_run(run, input_dir)
        if parsed is None:
            legacy_run_ids.append(run["id"])
        else:
            telemetry_runs.append(parsed)

    test_samples: dict[str, list[tuple[float, int]]] = defaultdict(list)
    shard_samples: dict[int, list[dict[str, Any]]] = defaultdict(list)
    run_summaries: list[dict[str, Any]] = []
    for run in telemetry_runs:
        shard_totals: dict[int, float] = {}
        run_jobs: list[dict[str, Any]] = []
        for job in run["jobs"]:
            shard_index = job["shard_index"]
            total = sum(record["duration_seconds"] for record in job["records"])
            shard_totals[shard_index] = total
            shard_samples[shard_index].append(
                {
                    "duration_seconds": total,
                    "region": job["region"],
                }
            )
            for record in job["records"]:
                test_samples[record["test_id"]].append(
                    (record["duration_seconds"], shard_index)
                )
            run_jobs.append(
                {
                    "job_id": job["job_id"],
                    "job_name": job["job_name"],
                    "region": job["region"],
                    "shard_index": shard_index,
                    "record_count": job["record_count"],
                    "test_duration_seconds": total,
                }
            )
        run_summaries.append(
            {
                "id": run["id"],
                "head_sha": run["head_sha"],
                "run_started_at": run["run_started_at"],
                "html_url": run["html_url"],
                "jobs": sorted(run_jobs, key=lambda job: job["shard_index"]),
                "test_critical_path_seconds": max(shard_totals.values()),
                "test_shard_gap_seconds": abs(shard_totals[0] - shard_totals[1]),
            }
        )

    test_stats = []
    for test_id, samples in test_samples.items():
        durations = [duration for duration, _ in samples]
        test_stats.append(
            {
                "test_id": test_id,
                "sample_count": len(durations),
                "median_seconds": median(durations),
                "p90_seconds": percentile(durations, 0.9),
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "observed_shards": sorted({shard for _, shard in samples}),
            }
        )
    test_stats.sort(
        key=lambda item: (-(item["median_seconds"] or 0), item["test_id"])
    )

    shard_stats = []
    for shard_index in sorted(shard_samples):
        samples = shard_samples[shard_index]
        durations = [sample["duration_seconds"] for sample in samples]
        shard_stats.append(
            {
                "suite": "core",
                "shard_count": 2,
                "shard_index": shard_index,
                "sample_count": len(durations),
                "median_test_seconds": median(durations),
                "p90_test_seconds": percentile(durations, 0.9),
                "regions": sorted(
                    {sample["region"] for sample in samples if sample["region"]}
                ),
            }
        )

    return {
        "schema_version": 1,
        "repository": manifest.get("repository"),
        "workflow": manifest.get("workflow"),
        "branch": manifest.get("branch"),
        "selection": {
            "requested_runs": manifest.get("requested_runs"),
            "downloaded_successful_runs": len(runs),
            "telemetry_runs": len(telemetry_runs),
            "legacy_runs_without_telemetry": legacy_run_ids,
        },
        "telemetry": {
            "record_schema_version": TIMING_SCHEMA_VERSION,
            "marker": TIMING_PREFIX,
            "runs": run_summaries,
            "shard_stats": shard_stats,
            "test_stats": test_stats,
        },
        "notes": {
            "scope": "canonical composition branch only",
            "test_duration": "sum of parent-unittest perf_counter durations; excludes runner setup and teardown",
            "balancing": "Do not rebalance shards from a single telemetry run; use multiple canonical samples.",
        },
    }


def write_summary(report: dict[str, Any], path: Path) -> None:
    selection = report["selection"]
    telemetry = report["telemetry"]
    lines = [
        "## Composition unittest timing",
        "",
        f"Canonical telemetry runs: **{selection['telemetry_runs']}** / "
        f"{selection['downloaded_successful_runs']} downloaded successful run(s).",
        "",
        "> Do not rebalance shards from a single telemetry run; use multiple canonical samples.",
        "",
    ]
    shard_stats = telemetry["shard_stats"]
    if shard_stats:
        lines.extend(
            [
                "### Core shard test-time totals",
                "",
                "| Shard | Samples | Median test time | P90 test time | Regions |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for stat in shard_stats:
            regions = ", ".join(stat["regions"]) or "n/a"
            lines.append(
                f"| {stat['shard_index'] + 1}/2 | {stat['sample_count']} | "
                f"{stat['median_test_seconds']:.3f}s | {stat['p90_test_seconds']:.3f}s | {regions} |"
            )
        lines.append("")

    test_stats = telemetry["test_stats"]
    if test_stats:
        lines.extend(
            [
                "### Slowest parent unittests by median",
                "",
                "| Test | Samples | Median | P90 |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for stat in test_stats[:20]:
            lines.append(
                f"| `{stat['test_id']}` | {stat['sample_count']} | "
                f"{stat['median_seconds']:.3f}s | {stat['p90_seconds']:.3f}s |"
            )
        lines.append("")
    else:
        lines.extend(
            [
                "No sampled canonical run contained unittest timing telemetry yet.",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not read timing manifest: {exc}") from exc
    try:
        report = build_report(manifest, args.input_dir)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_summary(report, args.summary)
    except (OSError, ReportError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
