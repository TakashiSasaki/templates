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
REPOSITORY_ID = "repository-123"
RESOURCE_ID = "pull-request-123"


def candidate(**overrides: object) -> dict:
    value = {
        "repository": "TakashiSasaki/templates",
        "number": 123,
        "id": "PR_node_123",
        "provider_identity": {
            "provider": "fake",
            "repository_id": REPOSITORY_ID,
            "resource_id": RESOURCE_ID,
        },
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
        "provider_identity": {
            "provider": "fake",
            "repository_id": REPOSITORY_ID,
            "resource_id": RESOURCE_ID,
        },
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


@pytest.mark.parametrize(
    ("signal", "record"),
    [
        (
            "short_sha_in_text",
            {"identity": "review-1", "body": "1111111 is clean", "state": "commented"},
        ),
        (
            "clean_wording",
            {"identity": "review-2", "body": "clean", "state": "commented"},
        ),
        (
            "reaction_only",
            {"identity": "reaction-1", "content": "+1", "state": "reaction"},
        ),
        (
            "outdated_thread",
            {
                "identity": "thread-1",
                "body": "outdated thread",
                "is_outdated": True,
                "is_resolved": False,
            },
        ),
    ],
)
def test_weak_signals_do_not_infer_binding_or_approval(
    signal: str, record: dict
) -> None:
    del signal
    current = snapshot([record])

    assert current["binding_status"] == "stable"
    assert current["merge_authorization"] == "not_established"
    assert current["review_approval"] == "not_inferred"


def test_absence_of_a_new_review_does_not_establish_approval() -> None:
    current = snapshot([])

    assert current["review_approval"] == "not_inferred"
    assert current["merge_authorization"] == "not_established"


def test_outdated_thread_disappearance_does_not_establish_resolution() -> None:
    previous = snapshot(
        [
            {
                "identity": "thread-1",
                "body": "finding",
                "is_outdated": True,
                "is_resolved": False,
            }
        ]
    )
    current = snapshot([])

    diff = OBSERVATION.diff_snapshots(previous, current)

    assert diff["status"] == "changed"
    removed = [change for change in diff["changes"] if change["kind"] == "removed_observed"]
    assert len(removed) == 1
    assert removed[0]["semantic_resolution"] == "not_inferred"
    assert current["review_approval"] == "not_inferred"


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


def test_summary_bounds_large_nested_values_and_serialized_size() -> None:
    huge = "x" * 100_000
    diff = {
        "status": "changed",
        "meaningful_change": True,
        "counts": {"changed": 3},
        "changes": [
            {
                "surface": "comments",
                "kind": "changed",
                "identity": f"comment-{index}",
                "after": {
                    "identity": f"comment-{index}",
                    "body": huge,
                    "message": huge,
                    "diff_hunk": huge,
                    "nested": {"value": huge},
                },
            }
            for index in range(3)
        ],
        "unknowns": [],
    }

    summary = OBSERVATION.summarize_diff(
        diff,
        limit=3,
        snapshot_reference={"path": "/tmp/detail.json", "digest": "a" * 64},
    )

    assert (
        len(OBSERVATION.canonical_json(summary).encode("utf-8"))
        <= OBSERVATION.MODEL_SUMMARY_MAX_BYTES
    )
    assert summary["summary_truncated"] is True
    assert "detail_reference" in summary
    assert "sha256=" in json.dumps(summary)
    assert len(summary["changes"][0]["after"]["body"]) < len(huge)


def test_incomplete_previous_snapshot_does_not_create_added_changes() -> None:
    first = snapshot(
        [{"identity": "known", "body": "baseline"}],
        complete=False,
        comments_complete=False,
    )
    second = snapshot(
        [{"identity": "known", "body": "baseline"}, {"identity": "page-2", "body": "recovered"}],
    )

    diff = OBSERVATION.diff_snapshots(first, second)

    assert diff["status"] == "incomplete"
    assert diff["meaningful_change"] is False
    assert not any(change["kind"] == "added" for change in diff["changes"])
    assert any(change["kind"] == "newly_observed" for change in diff["changes"])
    assert "previous_snapshot_incomplete" in diff["unknowns"]


def test_changed_surface_set_fails_closed_and_reordering_is_harmless() -> None:
    first = OBSERVATION.build_snapshot(
        candidate=candidate(),
        observed_start=binding(),
        observed_end=binding(),
        surfaces={
            "comments": surface([{"identity": "comment-1", "body": "same"}]),
            "reviews": surface([]),
        },
        requested_surfaces=["comments", "reviews"],
        observation={"provider": "fake"},
    )
    reordered = OBSERVATION.build_snapshot(
        candidate=candidate(),
        observed_start=binding(),
        observed_end=binding(),
        surfaces={
            "comments": surface([{"identity": "comment-1", "body": "same"}]),
            "reviews": surface([]),
        },
        requested_surfaces=["reviews", "comments"],
        observation={"provider": "fake"},
    )
    added = OBSERVATION.build_snapshot(
        candidate=candidate(),
        observed_start=binding(),
        observed_end=binding(),
        surfaces={
            "comments": surface([{"identity": "comment-1", "body": "same"}]),
            "reviews": surface([]),
            "threads": surface([]),
        },
        requested_surfaces=["comments", "reviews", "threads"],
        observation={"provider": "fake"},
    )

    assert OBSERVATION.diff_snapshots(first, reordered)["status"] == "unchanged"
    changed = OBSERVATION.diff_snapshots(first, added)
    assert changed["status"] == "incomplete"
    assert changed["unknowns"] == ["requested_surface_set_changed"]


def test_fixture_is_anonymized_and_has_expected_shape() -> None:
    fixture = ROOT / "tests" / "fixtures" / "pr-state-observation" / "reordered.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))

    assert data["repository"] == "TakashiSasaki/templates"
    assert all(record["identity"].startswith("comment-") for record in data["records"])
    assert all("github.com" not in json.dumps(record) for record in data["records"])
