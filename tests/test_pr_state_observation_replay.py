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

HEAD = "1111111111111111111111111111111111111111"
BASE = "2222222222222222222222222222222222222222"


def _snapshot(state: dict) -> dict:
    return OBSERVATION.build_snapshot(
        candidate={
            "repository": "TakashiSasaki/templates",
            "number": 123,
            "id": "PR_node_123",
            "expected_head_sha": HEAD,
            "expected_base_sha": BASE,
            "dependencies": [],
        },
        observed_start={"head_sha": HEAD, "base_sha": BASE, "dependencies": []},
        observed_end={"head_sha": HEAD, "base_sha": BASE, "dependencies": []},
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
    previous = None
    for snapshot in snapshots:
        diff = OBSERVATION.diff_snapshots(previous, snapshot)
        summary = OBSERVATION.summarize_diff(
            diff,
            limit=1,
            snapshot_reference={"path": "/tmp/replay.json", "digest": snapshot["snapshot_digest"]},
        )
        metrics.append(
            {
                "state": snapshot["observation"]["started_at"],
                "full_snapshot_bytes": len(OBSERVATION.canonical_json(snapshot).encode()),
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
