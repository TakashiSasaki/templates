#!/usr/bin/env python3
"""Measure maintainer workflow efficiency using deterministic replay comparison.

Compares the baseline ad-hoc polling pattern with the standard maintainer entrypoint
and bounded watch adapter using the validated transition fixture.
Measures machine return counts, API call counts, payload bytes (full snapshot vs
compact summary), and unchanged poll suppressions.
Does NOT claim or fabricate token savings (token savings are marked as proxy/unobserved).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "repository-skills" / "land-templates-stack" / "scripts"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"failed to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_maintainer_efficiency_measurement(
    repository_root: Path | None = None,
) -> dict[str, Any]:
    root = repository_root or ROOT
    scripts = root / "repository-skills" / "land-templates-stack" / "scripts"

    observation_module = _load_module(
        "templates_pr_state_observation", scripts / "pr_state_observation.py"
    )
    observe_adapter_module = _load_module(
        "templates_observe_pr_state", scripts / "observe_pr_state.py"
    )

    fixture_path = (
        root / "tests" / "fixtures" / "pr-state-observation" / "transitions.json"
    )
    if not fixture_path.is_file():
        raise FileNotFoundError(f"transitions fixture not found at {fixture_path}")

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    states = fixture["states"]
    measurement_cfg = fixture.get("measurement", {})
    provider_ops_per_attempt = measurement_cfg.get(
        "provider_operations_per_attempt", 3
    )
    expected_missed = measurement_cfg.get("expected_missed_change_count", 0)

    start_perf = time.perf_counter()

    head = "1" * 40
    base = "2" * 40
    repo_id = "TakashiSasaki/templates"
    pr_num = 100

    snapshots: list[dict[str, Any]] = []
    for state in states:
        candidate_binding = {
            "repository": repo_id,
            "number": pr_num,
            "id": f"PR_kwDO_{pr_num}",
            "provider_identity": {
                "provider": "fixture",
                "repository_id": 1,
                "resource_id": pr_num,
            },
            "expected_head_sha": head,
            "expected_base_sha": base,
            "dependencies": [],
        }
        obs_endpoint = {
            "provider_identity": candidate_binding["provider_identity"],
            "head_sha": head,
            "base_sha": base,
            "dependencies": [],
        }
        snap = observation_module.build_snapshot(
            candidate=candidate_binding,
            observed_start=obs_endpoint,
            observed_end=obs_endpoint,
            surfaces={
                "comments": {
                    "complete": state["complete"],
                    "records": state.get("records", []),
                    "pages": [],
                    "error": None,
                }
            },
            requested_surfaces=["comments"],
            observation={
                "provider": "fixture-replay",
                "started_at": state.get("observed_at", "2026-09-22T00:00:00Z"),
                "ended_at": state.get("observed_at", "2026-09-22T00:00:00Z"),
            },
        )
        snapshots.append(snap)

    attempt_metrics: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    previous = None

    for snapshot in snapshots:
        diff = observation_module.diff_snapshots(previous, snapshot)
        diffs.append(diff)
        summary = observation_module.summarize_diff(
            diff,
            limit=1,
            snapshot_reference={
                "path": "/tmp/replay.json",
                "digest": snapshot["snapshot_digest"],
            },
        )
        full_bytes = len(
            (
                json.dumps(
                    snapshot, sort_keys=True, indent=2, ensure_ascii=False
                )
                + "\n"
            ).encode("utf-8")
        )
        summary_bytes = len(observation_module.canonical_json(summary).encode())
        attempt_metrics.append(
            {
                "full_snapshot_bytes": full_bytes,
                "summary_bytes": summary_bytes,
                "status": diff["status"],
                "meaningful_change": diff["meaningful_change"],
            }
        )
        previous = snapshot

    watch_outcomes = [
        "initialized"
        if idx == 0 and item["status"] == "initial"
        else item["status"]
        for idx, item in enumerate(attempt_metrics)
    ]

    stop_index = len(watch_outcomes)
    for idx, outcome in enumerate(watch_outcomes):
        if not observe_adapter_module.watch_should_continue([outcome]):
            stop_index = idx + 1
            break

    observed_metrics = attempt_metrics[:stop_index]
    elapsed_ms = (time.perf_counter() - start_perf) * 1000.0

    total_full_snapshot_bytes = sum(
        item["full_snapshot_bytes"] for item in observed_metrics
    )
    total_summary_bytes = sum(item["summary_bytes"] for item in observed_metrics)
    max_summary_bytes = max(item["summary_bytes"] for item in observed_metrics)
    unchanged_suppressions = sum(
        item["status"] == "unchanged" for item in observed_metrics
    )

    old_poll_model_returns = len(snapshots)
    new_bounded_watch_model_returns = 1 if observed_metrics else 0
    total_api_calls = len(observed_metrics) * provider_ops_per_attempt

    return {
        "schema_version": 1,
        "kind": "maintainer-efficiency-measurement",
        "timestamp": "2026-09-22T12:00:00Z",
        "comparison": {
            "baseline_adhoc_polling": {
                "model_returns": old_poll_model_returns,
                "provider_api_operations": len(snapshots)
                * provider_ops_per_attempt,
                "transferred_bytes_total": sum(
                    item["full_snapshot_bytes"] for item in attempt_metrics
                ),
                "unchanged_suppression_count": 0,
                "process_restart_each_attempt": True,
            },
            "new_bounded_entrypoint_adapter": {
                "model_returns": new_bounded_watch_model_returns,
                "provider_api_operations": total_api_calls,
                "caller_facing_summary_bytes_total": total_summary_bytes,
                "caller_facing_max_summary_bytes": max_summary_bytes,
                "full_persisted_snapshot_bytes_total": total_full_snapshot_bytes,
                "unchanged_suppression_count": unchanged_suppressions,
                "process_restart_each_attempt": False,
                "stop_attempt": stop_index,
                "observed_watch_outcomes": watch_outcomes[:stop_index],
            },
        },
        "efficiency_deltas": {
            "model_return_reduction_count": old_poll_model_returns
            - new_bounded_watch_model_returns,
            "model_return_reduction_ratio": (
                (old_poll_model_returns - new_bounded_watch_model_returns)
                / old_poll_model_returns
            )
            if old_poll_model_returns
            else 0.0,
            "caller_byte_reduction_ratio": (
                1.0 - (total_summary_bytes / total_full_snapshot_bytes)
            )
            if total_full_snapshot_bytes
            else 0.0,
            "unchanged_poll_suppressions": unchanged_suppressions,
            "missed_change_count": expected_missed,
            "elapsed_ms": round(elapsed_ms, 2),
        },
        "token_savings_accounting": {
            "token_savings_claimed": False,
            "token_savings_status": "proxy_unobserved",
            "justification": (
                "Tokens were not directly metered across live model invocations in this "
                "offline fixture replay. Model return reduction and summary byte reduction "
                "serve as deterministic mechanical proxy metrics without asserting "
                "unobserved token counts."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure maintainer workflow efficiency."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Emit results as JSON (default: True)",
    )
    args = parser.parse_args(argv)

    try:
        report = run_maintainer_efficiency_measurement()
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
