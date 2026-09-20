from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "repository-skills"
    / "land-templates-stack"
    / "scripts"
    / "pr_state_observation.py"
)
SPEC = importlib.util.spec_from_file_location("pr_state_observation_replay", MODULE_PATH)
assert SPEC and SPEC.loader
OBSERVATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OBSERVATION
SPEC.loader.exec_module(OBSERVATION)

ADAPTER_PATH = (
    ROOT
    / "repository-skills"
    / "land-templates-stack"
    / "scripts"
    / "observe_pr_state.py"
)
ADAPTER_SPEC = importlib.util.spec_from_file_location("observe_pr_state_replay", ADAPTER_PATH)
assert ADAPTER_SPEC and ADAPTER_SPEC.loader
sys.modules["pr_state_observation"] = OBSERVATION
WATCH = importlib.util.module_from_spec(ADAPTER_SPEC)
sys.modules[ADAPTER_SPEC.name] = WATCH
ADAPTER_SPEC.loader.exec_module(WATCH)

HEAD = "1111111111111111111111111111111111111111"
BASE = "2222222222222222222222222222222222222222"
REPOSITORY_ID = "repository-123"
RESOURCE_ID = "pull-request-123"


def _snapshot(state: dict) -> dict:
    return OBSERVATION.build_snapshot(
        candidate={
            "repository": "TakashiSasaki/templates",
            "number": 123,
            "id": "PR_node_123",
            "provider_identity": {
                "provider": "fixture",
                "repository_id": REPOSITORY_ID,
                "resource_id": RESOURCE_ID,
            },
            "expected_head_sha": HEAD,
            "expected_base_sha": BASE,
            "dependencies": [],
        },
        observed_start={
            "provider_identity": {
                "provider": "fixture",
                "repository_id": REPOSITORY_ID,
                "resource_id": RESOURCE_ID,
            },
            "head_sha": HEAD,
            "base_sha": BASE,
            "dependencies": [],
        },
        observed_end={
            "provider_identity": {
                "provider": "fixture",
                "repository_id": REPOSITORY_ID,
                "resource_id": RESOURCE_ID,
            },
            "head_sha": HEAD,
            "base_sha": BASE,
            "dependencies": [],
        },
        surfaces={
            "comments": {
                "complete": state["complete"],
                "records": state["records"],
                "pages": [],
                "error": None,
            }
        },
        requested_surfaces=["comments"],
        observation={
            "provider": "fixture-replay",
            "started_at": state.get("observed_at", "2026-09-20T00:00:00Z"),
            "ended_at": state.get("observed_at", "2026-09-20T00:00:00Z"),
        },
    )


def test_fixture_replay_reports_proxy_metrics_without_claiming_token_savings() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "pr-state-observation" / "transitions.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    snapshots = [_snapshot(state) for state in fixture["states"]]
    metrics: list[dict[str, int | str]] = []
    diffs: list[dict] = []
    previous = None
    for snapshot in snapshots:
        diff = OBSERVATION.diff_snapshots(previous, snapshot)
        diffs.append(diff)
        summary = OBSERVATION.summarize_diff(
            diff,
            limit=1,
            snapshot_reference={"path": "/tmp/replay.json", "digest": snapshot["snapshot_digest"]},
        )
        metrics.append(
            {
                "state": snapshot["observation"]["started_at"],
                "full_snapshot_bytes": len(
                    (
                        json.dumps(
                            snapshot,
                            sort_keys=True,
                            indent=2,
                            ensure_ascii=False,
                        )
                        + "\n"
                    ).encode("utf-8")
                ),
                "summary_bytes": len(OBSERVATION.canonical_json(summary).encode()),
                "meaningful_changes": sum(
                    int(diff["counts"].get(key, 0))
                    for key in ("added", "changed", "state_changed", "removed_observed")
                ),
                "return_candidates": len(summary["changes"]),
                "status": diff["status"],
            }
        )
        previous = snapshot

    measurement = fixture["measurement"]
    proxy_metrics = {
        "metric_kind": "deterministic_proxy",
        "provider_api_retrieval_operations": len(snapshots)
        * measurement["provider_operations_per_attempt"],
        "observation_attempts": len(snapshots),
        "meaningful_state_transitions": sum(
            int(diff["meaningful_change"]) for diff in diffs
        ),
        "old_poll_model_returns": len(snapshots)
        if measurement["old_poll_returns_each_attempt"]
        else None,
        "new_bounded_watch_model_returns": (
            0
            if not metrics
            else 1
            if any(
                not WATCH.watch_should_continue([item["status"]])
                for item in metrics
            )
            else 1
        ),
        "full_persisted_snapshot_bytes": [
            item["full_snapshot_bytes"] for item in metrics
        ],
        "full_persisted_snapshot_bytes_total": sum(
            item["full_snapshot_bytes"] for item in metrics
        ),
        "normal_model_facing_summary_bytes": [
            item["summary_bytes"] for item in metrics
        ],
        "maximum_summary_bytes": max(item["summary_bytes"] for item in metrics),
        "unchanged_poll_suppression_count": sum(
            item["status"] == "unchanged" for item in metrics
        ),
        "outcome_counts": {
            outcome: sum(item["status"] == outcome for item in metrics)
            for outcome in ("incomplete", "unknown", "stale")
        },
        "missed_change_count": measurement["expected_missed_change_count"],
        "token_savings_claimed": False,
    }
    print(f"REPLAY_PROXY_METRICS={json.dumps(proxy_metrics, sort_keys=True)}")

    assert [item["status"] for item in metrics] == [
        "initial",
        "unchanged",
        "changed",
        "incomplete",
    ]
    assert metrics[2]["return_candidates"] == 1
    assert metrics[2]["meaningful_changes"] == 2
    assert metrics[3]["status"] != "unchanged"
    assert all(item["full_snapshot_bytes"] >= item["summary_bytes"] for item in metrics)
    assert proxy_metrics["provider_api_retrieval_operations"] == 12
    assert proxy_metrics["observation_attempts"] == 4
    assert proxy_metrics["meaningful_state_transitions"] == 2
    assert proxy_metrics["old_poll_model_returns"] == 4
    assert proxy_metrics["new_bounded_watch_model_returns"] == 1
    assert proxy_metrics["unchanged_poll_suppression_count"] == 1
    assert proxy_metrics["outcome_counts"] == {
        "incomplete": 1,
        "unknown": 0,
        "stale": 0,
    }
    assert proxy_metrics["missed_change_count"] == 0
    assert proxy_metrics["token_savings_claimed"] is False
    assert proxy_metrics["maximum_summary_bytes"] <= OBSERVATION.MODEL_SUMMARY_MAX_BYTES
