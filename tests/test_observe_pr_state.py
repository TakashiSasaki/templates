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
    / "observe_pr_state.py"
)
SPEC = importlib.util.spec_from_file_location("observe_pr_state", MODULE_PATH)
assert SPEC and SPEC.loader
OBSERVE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OBSERVE
SPEC.loader.exec_module(OBSERVE)


HEAD = "1111111111111111111111111111111111111111"
BASE = "2222222222222222222222222222222222222222"
OTHER_HEAD = "3333333333333333333333333333333333333333"


def candidate(
    *,
    identifier: str = "PR_node_123",
    head: str = HEAD,
    base: str = BASE,
    dependencies: list[dict] | None = None,
) -> OBSERVE.CandidateBinding:
    return OBSERVE.CandidateBinding.from_mapping(
        {
            "repository": "TakashiSasaki/templates",
            "number": 123,
            "id": identifier,
            "expected_head_sha": head,
            "expected_base_sha": base,
            "dependencies": [] if dependencies is None else dependencies,
        }
    )


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
    pages: list[dict] | None = None,
) -> dict:
    return {
        "complete": complete,
        "records": records,
        "pages": [] if pages is None else pages,
        "error": None,
    }


class FakeClock:
    def __init__(self, now: float = 0.0, *, cancel_on_sleep: bool = False) -> None:
        self.now = now
        self.sleeps: list[float] = []
        self.cancel_on_sleep = cancel_on_sleep

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if self.cancel_on_sleep:
            raise OBSERVE.ObservationCancelled()
        self.now += seconds


class FakeProvider:
    def __init__(
        self,
        bindings: list[dict],
        surfaces: dict[str, list[dict | Exception]],
    ) -> None:
        self.bindings = list(bindings)
        self.surfaces = {name: list(values) for name, values in surfaces.items()}
        self.binding_calls = 0

    def read_binding(self, candidate: OBSERVE.CandidateBinding) -> dict:
        del candidate
        index = min(self.binding_calls, len(self.bindings) - 1)
        self.binding_calls += 1
        value = self.bindings[index]
        if isinstance(value, Exception):
            raise value
        return value

    def read_surface(
        self,
        candidate: OBSERVE.CandidateBinding,
        surface_name: str,
        binding_value: dict,
    ) -> dict:
        del candidate, binding_value
        values = self.surfaces[surface_name]
        value = values.pop(0) if values else surface([], complete=True)
        if isinstance(value, Exception):
            raise value
        return value


def request(
    tmp_path: Path,
    *,
    mode: str = "single-shot",
    max_attempts: int = 1,
    deadline: float | None = None,
    previous: Path | None = None,
    surfaces: tuple[str, ...] = ("comments",),
) -> OBSERVE.ObservationRequest:
    return OBSERVE.ObservationRequest(
        candidates=(candidate(),),
        surfaces=surfaces,
        mode=mode,
        deadline=deadline,
        max_attempts=max_attempts,
        summary_limit=2,
        snapshot_path=tmp_path / "observation.json",
        previous_snapshot_path=previous,
    )


def run_observation(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    observation_request: OBSERVE.ObservationRequest | None = None,
    clock: FakeClock | None = None,
) -> dict:
    fake_clock = clock or FakeClock()
    return OBSERVE.observe(
        observation_request or request(tmp_path),
        provider,
        repository_root=tmp_path / "repo",
        clock=fake_clock,
        sleep=fake_clock.sleep,
    )


def test_single_shot_writes_complete_snapshot_and_bounded_summary(tmp_path: Path) -> None:
    provider = FakeProvider(
        [binding(), binding()],
        {
            "comments": [
                surface(
                    [
                        {"identity": "comment-1", "body": "finding", "state": "open"},
                    ]
                )
            ]
        },
    )

    result = run_observation(tmp_path, provider)
    summary = OBSERVE.bounded_summary(result, 1)
    saved = json.loads((tmp_path / "observation.json").read_text(encoding="utf-8"))

    assert result["outcome"] == "initialized"
    assert saved["snapshots"]["PR_node_123"]["complete"] is True
    assert summary["candidates"][0]["outcome"] == "initialized"
    assert summary["merge_authorization"] == "not_established"


def test_same_snapshot_again_is_unchanged_and_does_not_reprint_detail(tmp_path: Path) -> None:
    first_provider = FakeProvider(
        [binding(), binding()],
        {"comments": [surface([{"identity": "comment-1", "body": "same"}])]},
    )
    first = run_observation(tmp_path, first_provider)

    second_provider = FakeProvider(
        [binding(), binding()],
        {"comments": [surface([{"identity": "comment-1", "body": "same"}])]},
    )
    second_request = request(tmp_path, previous=tmp_path / "observation.json")
    second = run_observation(tmp_path, second_provider, observation_request=second_request)
    summary = OBSERVE.bounded_summary(second, 1)

    assert first["outcome"] == "initialized"
    assert second["outcome"] == "unchanged"
    assert summary["candidates"][0]["diff"]["changes"] == []
    assert "body" not in json.dumps(summary)


def test_pagination_keeps_more_than_100_records_and_empty_middle_page(tmp_path: Path) -> None:
    records = [
        {"identity": f"comment-{index}", "body": f"body-{index}"}
        for index in range(101)
    ]
    provider = FakeProvider(
        [binding(), binding()],
        {
            "comments": [
                surface(
                    records,
                    pages=[
                        {"page_index": 0, "item_count": 100},
                        {"page_index": 1, "item_count": 0},
                        {"page_index": 2, "item_count": 1},
                    ],
                )
            ]
        },
    )

    result = run_observation(tmp_path, provider)
    snapshot = result["snapshots"]["PR_node_123"]

    assert result["outcome"] == "initialized"
    assert len(snapshot["surfaces"]["comments"]["records"]) == 101
    assert snapshot["surfaces"]["comments"]["pages"][1]["item_count"] == 0


def test_page_failure_is_incomplete_not_unchanged(tmp_path: Path) -> None:
    provider = FakeProvider(
        [binding(), binding()],
        {
            "comments": [
                OBSERVE.ProviderFailure("incomplete", "page 2 failed"),
            ]
        },
    )

    result = run_observation(tmp_path, provider)

    assert result["outcome"] == "incomplete"
    assert result["candidates"][0]["error"] is None if "error" in result["candidates"][0] else True
    assert result["snapshots"]["PR_node_123"]["complete"] is False


def test_binding_head_base_and_dependency_change_is_stale(tmp_path: Path) -> None:
    dependency = {
        "id": "policy-pr-1",
        "authority": "policy",
        "expected_head_sha": HEAD,
        "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
    }
    bound_candidate = candidate(dependencies=[dependency])
    provider = FakeProvider(
        [
            binding(dependencies=[{"id": "policy-pr-1", "head_sha": HEAD}]),
            binding(
                head=OTHER_HEAD,
                base=OTHER_HEAD,
                dependencies=[{"id": "policy-pr-1", "head_sha": OTHER_HEAD}],
            ),
        ],
        {"comments": [surface([{"identity": "comment-1", "body": "data"}])]},
    )
    observation_request = OBSERVE.ObservationRequest(
        candidates=(bound_candidate,),
        surfaces=("comments",),
        mode="single-shot",
        deadline=None,
        max_attempts=1,
        summary_limit=2,
        snapshot_path=tmp_path / "observation.json",
        previous_snapshot_path=None,
    )

    result = run_observation(
        tmp_path,
        provider,
        observation_request=observation_request,
    )

    assert result["outcome"] == "stale"
    assert "candidate_changed_during_observation" in result["snapshots"][
        "PR_node_123"
    ]["binding_reasons"]
    assert any(
        "dependency_changed" in reason
        for reason in result["snapshots"]["PR_node_123"]["binding_reasons"]
    )


def test_permission_failure_is_unknown_not_unchanged(tmp_path: Path) -> None:
    provider = FakeProvider(
        [OBSERVE.ProviderFailure("permission", "403 forbidden")],
        {"comments": []},
    )

    result = run_observation(tmp_path, provider)

    assert result["outcome"] == "unknown"
    assert result["candidates"][0]["outcome"] == "unknown"
    assert result["candidates"][0]["error"]["category"] == "permission"


def test_watch_respects_backoff_and_deadline(tmp_path: Path) -> None:
    clock = FakeClock()
    provider = FakeProvider(
        [binding()] * 6,
        {"comments": [surface([{"identity": "comment-1", "body": "same"}])] * 3},
    )
    observation_request = request(
        tmp_path,
        mode="watch",
        max_attempts=2,
        deadline=100.0,
    )

    result = run_observation(
        tmp_path,
        provider,
        observation_request=observation_request,
        clock=clock,
    )

    assert result["outcome"] == "deadline_reached"
    assert result["termination"] == "deadline"
    assert clock.sleeps == [1.0]
    assert result["resume"]["last_attempt"] == 2


def test_watch_cancel_returns_resume_reason(tmp_path: Path) -> None:
    clock = FakeClock(cancel_on_sleep=True)
    provider = FakeProvider(
        [binding(), binding()],
        {"comments": [surface([{"identity": "comment-1", "body": "same"}])]},
    )
    observation_request = request(
        tmp_path,
        mode="watch",
        max_attempts=3,
        deadline=100.0,
    )

    result = run_observation(
        tmp_path,
        provider,
        observation_request=observation_request,
        clock=clock,
    )

    assert result["outcome"] == "cancelled"
    assert result["termination"] == "cancelled"
    assert result["resume"]["reason"] == "cancelled"


def test_previous_snapshot_candidate_mismatch_is_stale(tmp_path: Path) -> None:
    first_provider = FakeProvider(
        [binding(), binding()],
        {"comments": [surface([{"identity": "comment-1", "body": "old"}])]},
    )
    run_observation(tmp_path, first_provider)

    changed_candidate = candidate(head=OTHER_HEAD)
    second_provider = FakeProvider(
        [
            binding(head=OTHER_HEAD),
            binding(head=OTHER_HEAD),
        ],
        {"comments": [surface([{"identity": "comment-1", "body": "new"}])]},
    )
    second_request = OBSERVE.ObservationRequest(
        candidates=(changed_candidate,),
        surfaces=("comments",),
        mode="single-shot",
        deadline=None,
        max_attempts=1,
        summary_limit=2,
        snapshot_path=tmp_path / "second.json",
        previous_snapshot_path=tmp_path / "observation.json",
    )

    result = run_observation(
        tmp_path,
        second_provider,
        observation_request=second_request,
    )

    assert result["outcome"] == "stale"


def test_check_records_keep_old_success_and_current_failure_separate() -> None:
    candidate_value = candidate()
    responses = {
        "check-runs": OBSERVE.ApiResponse(
            [
                {
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "same-workflow",
                            "status": "completed",
                            "conclusion": "success",
                        },
                        {
                            "id": 2,
                            "name": "same-workflow",
                            "status": "completed",
                            "conclusion": "failure",
                        },
                    ]
                }
            ]
        ),
        "status": OBSERVE.ApiResponse([{"statuses": []}]),
    }

    def api(arguments: tuple[str, ...]) -> OBSERVE.ApiResponse:
        endpoint = arguments[-1]
        for key, response in responses.items():
            if key in endpoint:
                return response
        raise AssertionError(arguments)

    provider = OBSERVE.GhReadonlyProvider(api)
    result = provider._checks(candidate_value, HEAD)

    assert len(result["records"]) == 2
    assert {record["identity"] for record in result["records"]} == {
        "check-run:1",
        "check-run:2",
    }
    assert {record["conclusion"] for record in result["records"]} == {
        "success",
        "failure",
    }


def test_reactions_cover_pr_issue_and_comment_surfaces() -> None:
    calls: list[tuple[str, ...]] = []

    def api(arguments: tuple[str, ...]) -> OBSERVE.ApiResponse:
        calls.append(arguments)
        endpoint = arguments[-1]
        if endpoint.endswith("/issues/123/comments"):
            return OBSERVE.ApiResponse([[{"id": 11}]])
        if endpoint.endswith("/pulls/123/comments"):
            return OBSERVE.ApiResponse([[{"id": 22}]])
        if endpoint.endswith("/issues/123/reactions"):
            return OBSERVE.ApiResponse([[{"id": 1, "content": "+1"}]])
        if endpoint.endswith("/issues/comments/11/reactions"):
            return OBSERVE.ApiResponse([[{"id": 2, "content": "heart"}]])
        if endpoint.endswith("/pulls/comments/22/reactions"):
            return OBSERVE.ApiResponse([[{"id": 3, "content": "rocket"}]])
        raise AssertionError(arguments)

    provider = OBSERVE.GhReadonlyProvider(api)
    result = provider._reactions(candidate())

    assert result["complete"] is True
    assert {
        record["identity"] for record in result["records"]
    } == {
        "pull_request:123:reaction:1",
        "issue_comment:11:reaction:2",
        "review_comment:22:reaction:3",
    }
    assert all("--paginate" in call for call in calls)


def test_write_methods_and_malformed_responses_fail_closed() -> None:
    with pytest.raises(OBSERVE.ObservationInputError, match="write methods"):
        OBSERVE.gh_api_json(("POST", "/repos/TakashiSasaki/templates/pulls/1"))

    def malformed(_: tuple[str, ...]) -> OBSERVE.ApiResponse:
        return OBSERVE.ApiResponse({"not": "a pull request"})

    provider = OBSERVE.GhReadonlyProvider(malformed)
    with pytest.raises(OBSERVE.ProviderFailure, match="pull request head"):
        provider.read_binding(candidate())
