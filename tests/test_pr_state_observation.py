from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "repository-skills"
    / "land-templates-stack"
    / "scripts"
    / "pr_state_observation.py"
)
SPEC = importlib.util.spec_from_file_location("pr_state_observation", MODULE_PATH)
assert SPEC and SPEC.loader
OBSERVATION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OBSERVATION
SPEC.loader.exec_module(OBSERVATION)


HEAD = "1111111111111111111111111111111111111111"
BASE = "2222222222222222222222222222222222222222"


def candidate(**overrides: object) -> dict:
    value = {
        "repository": "TakashiSasaki/templates",
        "number": 123,
        "id": "PR_node_123",
        "expected_head_sha": HEAD,
        "expected_base_sha": BASE,
        "dependencies": [],
    }
    value.update(overrides)
    return value


def binding(
    *,
    head: str = HEAD,
    base: str = BASE,
    dependencies: list[dict] | None = None,
) -> dict:
    return {
        "head_sha": head,
        "base_sha": base,
        "dependencies": [] if dependencies is None else dependencies,
    }


def surface(
    records: list[dict],
    *,
    complete: bool = True,
    error: dict | None = None,
) -> dict:
    return {"complete": complete, "records": records, "pages": [], "error": error}


def snapshot(
    records: list[dict],
    *,
    complete: bool = True,
    start: dict | None = None,
    end: dict | None = None,
    comments_complete: bool | None = None,
    candidate_value: dict | None = None,
) -> dict:
    comments = surface(
        records,
        complete=complete if comments_complete is None else comments_complete,
    )
    return OBSERVATION.build_snapshot(
        candidate=candidate_value or candidate(),
        observed_start=start or binding(),
        observed_end=end or binding(),
        surfaces={"comments": comments},
        requested_surfaces=["comments"],
        observation={
            "provider": "fake",
            "started_at": "2026-09-20T00:00:00Z",
            "ended_at": "2026-09-20T00:00:01Z",
        },
    )


def test_same_content_different_order_and_observation_time_is_unchanged() -> None:
    first = snapshot(
        [
            {
                "identity": "c-2",
                "body": "second",
                "state": "visible",
                "observed_at": "a",
            },
            {
                "identity": "c-1",
                "body": "first",
                "state": "visible",
                "observed_at": "b",
            },
        ]
    )
    second = snapshot(
        [
            {
                "identity": "c-1",
                "body": "first",
                "state": "visible",
                "observed_at": "later",
            },
            {
                "identity": "c-2",
                "body": "second",
                "state": "visible",
                "observed_at": "latest",
            },
        ]
    )

    diff = OBSERVATION.diff_snapshots(first, second)

    assert diff["status"] == "unchanged"
    assert diff["meaningful_change"] is False
    assert second["complete"] is True


def test_new_inline_content_edit_and_explicit_dismissal_are_returned() -> None:
    first = snapshot(
        [
            {"identity": "inline-1", "body": "old", "state": "open"},
            {"identity": "review-1", "body": "review", "state": "submitted"},
        ]
    )
    second = snapshot(
        [
            {"identity": "inline-1", "body": "edited", "state": "open"},
            {"identity": "review-1", "body": "review", "state": "dismissed"},
            {"identity": "inline-2", "body": "new finding", "state": "open"},
        ]
    )

    diff = OBSERVATION.diff_snapshots(first, second)

    assert diff["status"] == "changed"
    assert {change["kind"] for change in diff["changes"]} == {
        "changed",
        "state_changed",
        "added",
    }
    assert any(
        change.get("record", {}).get("body") == "new finding"
        for change in diff["changes"]
    )
    assert all(
        change.get("semantic_resolution") != "approved" for change in diff["changes"]
    )


def test_missing_unresolved_record_in_incomplete_observation_is_not_resolution() -> None:
    first = snapshot([{"identity": "finding-1", "body": "keep open", "state": "open"}])
    second = snapshot(
        [],
        complete=False,
        comments_complete=False,
    )

    diff = OBSERVATION.diff_snapshots(first, second)

    assert diff["status"] == "incomplete"
    assert diff["counts"]["removed_observed"] == 0
    assert diff["counts"]["not_observed"] >= 1
    assert diff["changes"][0]["kind"] == "not_observed"
    assert diff["changes"][0]["semantic_resolution"] == "not_inferred"


def test_binding_change_is_stale_and_does_not_mix_candidates() -> None:
    first = snapshot([{"identity": "c-1", "body": "old", "state": "visible"}])
    second = snapshot(
        [{"identity": "c-1", "body": "new candidate", "state": "visible"}],
        start=binding(head="3333333333333333333333333333333333333333"),
        end=binding(head="3333333333333333333333333333333333333333"),
    )

    diff = OBSERVATION.diff_snapshots(first, second)

    assert diff["status"] == "stale"
    assert second["binding_status"] == "stale"
    assert any("expected_head" in reason for reason in second["binding_reasons"])


def test_identity_is_required_and_check_name_cannot_be_used_as_identity() -> None:
    with pytest.raises(OBSERVATION.ObservationInputError, match="stable provider identity"):
        snapshot([{"name": "same check", "state": "success"}])


def test_summary_limit_preserves_continuation_reference() -> None:
    diff = {
        "status": "changed",
        "meaningful_change": True,
        "counts": {"added": 3},
        "changes": [
            {"surface": "comments", "kind": "added", "identity": f"c-{i}"}
            for i in range(3)
        ],
        "unknowns": [],
    }

    summary = OBSERVATION.summarize_diff(
        diff,
        limit=1,
        snapshot_reference={"path": "/tmp/snapshot.json", "digest": "a" * 64},
    )

    assert summary["summary_truncated"] is True
    assert summary["omitted_change_count"] == 2
    assert summary["continuation"]["offset"] == 1
    assert summary["merge_authorization"] == "not_established"


def test_summary_keeps_finding_and_check_fields_without_replaying_large_payloads() -> None:
    diff = {
        "status": "changed",
        "meaningful_change": True,
        "counts": {"changed": 1},
        "changes": [
            {
                "surface": "checks",
                "kind": "changed",
                "identity": "check-run:1",
                "after": {
                    "identity": "check-run:1",
                    "name": "apply",
                    "status": "completed",
                    "conclusion": "failure",
                    "app": {"events": ["many"], "permissions": {"contents": "write"}},
                },
            }
        ],
        "unknowns": [],
    }

    summary = OBSERVATION.summarize_diff(diff, limit=1)

    assert summary["changes"][0]["after"]["conclusion"] == "failure"
    assert "app" not in summary["changes"][0]["after"]


def test_fixture_is_anonymized_and_has_expected_shape() -> None:
    fixture = ROOT / "tests" / "fixtures" / "pr-state-observation" / "reordered.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))

    assert data["repository"] == "TakashiSasaki/templates"
    assert all(record["identity"].startswith("comment-") for record in data["records"])
    assert all("github.com" not in json.dumps(record) for record in data["records"])
