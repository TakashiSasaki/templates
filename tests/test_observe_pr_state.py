from __future__ import annotations

import importlib.util
import json
import subprocess
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
REPOSITORY_ID = "repository-123"
RESOURCE_ID = "pull-request-123"
OTHER_REPOSITORY_ID = "repository-999"
OTHER_RESOURCE_ID = "pull-request-999"


def candidate(
    *,
    identifier: str = "PR_node_123",
    head: str = HEAD,
    base: str = BASE,
    repository_id: str = REPOSITORY_ID,
    resource_id: str = RESOURCE_ID,
    dependencies: list[dict] | None = None,
) -> OBSERVE.CandidateBinding:
    normalized_dependencies = [
        {
            **item,
            "expected_base_sha": item.get("expected_base_sha", base),
        }
        for item in ([] if dependencies is None else dependencies)
    ]
    return OBSERVE.CandidateBinding.from_mapping(
        {
            "repository": "TakashiSasaki/templates",
            "number": 123,
            "id": identifier,
            "provider_identity": {
                "provider": "github",
                "repository_id": repository_id,
                "resource_id": resource_id,
            },
            "expected_head_sha": head,
            "expected_base_sha": base,
            "dependencies": normalized_dependencies,
        }
    )


def binding(
    *,
    head: str = HEAD,
    base: str = BASE,
    repository_id: str = REPOSITORY_ID,
    resource_id: str = RESOURCE_ID,
    dependencies: list[dict] | None = None,
) -> dict:
    normalized_dependencies = [
        {
            **item,
            "base_sha": item.get("base_sha", base),
        }
        for item in ([] if dependencies is None else dependencies)
    ]
    return {
        "provider_identity": {
            "provider": "github",
            "repository_id": repository_id,
            "resource_id": resource_id,
        },
        "head_sha": head,
        "base_sha": base,
        "dependencies": normalized_dependencies,
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
        surfaces: dict[str, list[dict | BaseException]],
        *,
        clock: FakeClock | None = None,
        advance_on_surface: float = 0.0,
    ) -> None:
        self.bindings = list(bindings)
        self.surfaces = {name: list(values) for name, values in surfaces.items()}
        self.binding_calls = 0
        self.clock = clock
        self.advance_on_surface = advance_on_surface
        self.surface_calls: list[tuple[str, str]] = []

    def read_binding(
        self,
        candidate: OBSERVE.CandidateBinding,
        *,
        budget: OBSERVE.ObservationBudget,
    ) -> dict:
        del candidate
        budget.check()
        index = min(self.binding_calls, len(self.bindings) - 1)
        self.binding_calls += 1
        value = self.bindings[index]
        if isinstance(value, BaseException):
            raise value
        return value

    def read_surface(
        self,
        candidate: OBSERVE.CandidateBinding,
        surface_name: str,
        binding_value: dict,
        *,
        budget: OBSERVE.ObservationBudget,
    ) -> dict:
        self.surface_calls.append((candidate.identifier, surface_name))
        del binding_value
        budget.check()
        values = self.surfaces[surface_name]
        value = values.pop(0) if values else surface([], complete=True)
        if isinstance(value, BaseException):
            raise value
        if self.clock is not None:
            self.clock.now += self.advance_on_surface
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


def unlimited_budget() -> OBSERVE.ObservationBudget:
    return OBSERVE.ObservationBudget(None, clock=lambda: 0.0)


def two_candidate_request(
    tmp_path: Path, *, previous: Path | None = None
) -> OBSERVE.ObservationRequest:
    return OBSERVE.ObservationRequest(
        candidates=(candidate(), candidate(identifier="PR_node_456")),
        surfaces=("comments",),
        mode="single-shot",
        deadline=None,
        max_attempts=1,
        summary_limit=2,
        snapshot_path=tmp_path / "observation.json",
        previous_snapshot_path=previous,
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
    assert result["candidates"][0]["error"]["category"] == "incomplete"
    assert result["snapshots"]["PR_node_123"]["complete"] is False


def test_surface_timeout_is_not_reclassified_as_incomplete_or_unchanged(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [binding(), binding()],
        {"comments": [OBSERVE.ProviderFailure("timeout", "request timed out")]},
    )

    result = run_observation(tmp_path, provider)

    assert result["outcome"] == "timed_out"
    assert result["candidates"][0]["outcome"] == "timed_out"
    assert result["candidates"][0]["error"]["category"] == "timeout"


def test_binding_head_base_and_dependency_change_is_stale(tmp_path: Path) -> None:
    dependency = {
        "id": "policy-pr-1",
        "authority": "policy",
        "expected_head_sha": HEAD,
        "provider_identity": {
            "provider": "github",
            "repository_id": "repository-1",
            "resource_id": "pull-request-1",
        },
        "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
    }
    bound_candidate = candidate(dependencies=[dependency])
    provider = FakeProvider(
        [
            binding(
                dependencies=[
                    {
                        "id": "policy-pr-1",
                        "head_sha": HEAD,
                        "provider_identity": {
                            "provider": "github",
                            "repository_id": "repository-1",
                            "resource_id": "pull-request-1",
                        },
                    }
                ]
            ),
            binding(
                head=OTHER_HEAD,
                base=OTHER_HEAD,
                dependencies=[
                    {
                        "id": "policy-pr-1",
                        "head_sha": OTHER_HEAD,
                        "provider_identity": {
                            "provider": "github",
                            "repository_id": "repository-1",
                            "resource_id": "pull-request-1",
                        },
                    }
                ],
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


def test_dependency_base_movement_is_stale_when_head_is_unchanged(tmp_path: Path) -> None:
    dependency = {
        "id": "policy-pr-1",
        "authority": "policy",
        "expected_head_sha": HEAD,
        "expected_base_sha": BASE,
        "provider_identity": {
            "provider": "github",
            "repository_id": "repository-1",
            "resource_id": "pull-request-1",
        },
        "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
    }
    observed_dependency = {
        "id": "policy-pr-1",
        "head_sha": HEAD,
        "base_sha": BASE,
        "provider_identity": dependency["provider_identity"],
    }
    moved_dependency = {
        **observed_dependency,
        "base_sha": OTHER_HEAD,
    }
    provider = FakeProvider(
        [
            binding(dependencies=[observed_dependency]),
            binding(dependencies=[moved_dependency]),
        ],
        {"comments": [surface([])]},
    )
    result = run_observation(
        tmp_path,
        provider,
        observation_request=OBSERVE.ObservationRequest(
            candidates=(candidate(dependencies=[dependency]),),
            surfaces=("comments",),
            mode="single-shot",
            deadline=None,
            max_attempts=1,
            summary_limit=2,
            snapshot_path=tmp_path / "observation.json",
            previous_snapshot_path=None,
        ),
    )

    assert result["outcome"] == "stale"
    assert "end_dependency_base_changed:policy-pr-1" in result["snapshots"][
        "PR_node_123"
    ]["binding_reasons"]


def test_github_binding_reads_repository_and_pull_request_immutable_ids() -> None:
    live_candidate = candidate(repository_id="123", resource_id="456")

    def metadata(*, pull_request_id: int, number: int = 123) -> dict:
        return {
            "id": pull_request_id,
            "number": number,
            "head": {"sha": HEAD},
            "base": {
                "sha": BASE,
                "repo": {"id": 123, "full_name": "TakashiSasaki/templates"},
            },
        }

    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        endpoint = arguments[-1]
        if endpoint.endswith("/pulls/123"):
            return OBSERVE.ApiResponse([metadata(pull_request_id=456)])
        if endpoint.endswith("/pulls/1"):
            return OBSERVE.ApiResponse([metadata(pull_request_id=789, number=1)])
        raise AssertionError(arguments)

    dependency = candidate(
        dependencies=[
            {
                "id": "policy-pr-1",
                "authority": "policy",
                "expected_head_sha": HEAD,
                "provider_identity": {
                    "provider": "github",
                    "repository_id": "123",
                    "resource_id": "789",
                },
                "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
            }
        ]
    ).dependencies[0]
    live_candidate = OBSERVE.CandidateBinding(
        live_candidate.repository,
        live_candidate.number,
        live_candidate.identifier,
        live_candidate.provider_identity,
        live_candidate.expected_head_sha,
        live_candidate.expected_base_sha,
        (dependency,),
    )
    provider = OBSERVE.GhReadonlyProvider(api)

    binding_value = provider.read_binding(live_candidate, budget=unlimited_budget())

    assert binding_value["provider_identity"] == {
        "provider": "github",
        "repository_id": "123",
        "resource_id": "456",
    }
    assert binding_value["dependencies"][0]["provider_identity"]["resource_id"] == "789"
    assert binding_value["dependencies"][0]["base_sha"] == BASE


def test_github_dependency_missing_base_is_incomplete() -> None:
    live_candidate = candidate(
        repository_id="123",
        resource_id="456",
        dependencies=[
            {
                "id": "policy-pr-1",
                "authority": "policy",
                "expected_head_sha": HEAD,
                "expected_base_sha": BASE,
                "provider_identity": {
                    "provider": "github",
                    "repository_id": "123",
                    "resource_id": "789",
                },
                "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
            }
        ],
    )

    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        endpoint = arguments[-1]
        if endpoint.endswith("/pulls/123"):
            return OBSERVE.ApiResponse(
                [
                    {
                        "id": 456,
                        "number": 123,
                        "head": {"sha": HEAD},
                        "base": {
                            "sha": BASE,
                            "repo": {
                                "id": 123,
                                "full_name": "TakashiSasaki/templates",
                            },
                        },
                    }
                ]
            )
        if endpoint.endswith("/pulls/1"):
            return OBSERVE.ApiResponse(
                [
                    {
                        "id": 789,
                        "number": 1,
                        "head": {"sha": HEAD},
                        "base": {
                            "repo": {
                                "id": 123,
                                "full_name": "TakashiSasaki/templates",
                            }
                        },
                    }
                ]
            )
        raise AssertionError(arguments)

    with pytest.raises(OBSERVE.ProviderFailure, match="dependency policy-pr-1 base"):
        OBSERVE.GhReadonlyProvider(api).read_binding(
            live_candidate, budget=unlimited_budget()
        )


def test_dependency_provider_path_identity_mismatch_is_stale_even_with_matching_sha() -> None:
    declared_dependency = {
        "id": "policy-pr-1",
        "authority": "policy",
        "expected_head_sha": HEAD,
        "provider_identity": {
            "provider": "github",
            "repository_id": "123",
            "resource_id": "expected-dependency",
        },
        "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
    }
    live_candidate = candidate(
        repository_id="123",
        resource_id="456",
        dependencies=[declared_dependency],
    )

    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        endpoint = arguments[-1]
        live_id = 456 if endpoint.endswith("/pulls/123") else 999
        return OBSERVE.ApiResponse(
            [
                {
                    "id": live_id,
                    "number": 123 if live_id == 456 else 1,
                    "head": {"sha": HEAD},
                    "base": {
                        "sha": BASE,
                        "repo": {"id": 123, "full_name": "TakashiSasaki/templates"},
                    },
                }
            ]
        )

    provider = OBSERVE.GhReadonlyProvider(api)
    observed = provider.read_binding(live_candidate, budget=unlimited_budget())
    snapshot = OBSERVE.build_snapshot(
        candidate=live_candidate,
        observed_start=observed,
        observed_end=observed,
        surfaces={"comments": surface([])},
        requested_surfaces=["comments"],
        observation={"provider": "fake"},
    )

    assert snapshot["binding_status"] == "stale"
    assert any(
        "dependency_provider_identity_mismatch" in reason
        for reason in snapshot["binding_reasons"]
    )


def test_github_repository_identity_mismatch_is_stale_even_with_matching_sha() -> None:
    live_candidate = candidate(repository_id="expected-repository", resource_id="456")

    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del arguments, timeout
        return OBSERVE.ApiResponse(
            [
                {
                    "id": 456,
                    "number": 123,
                    "head": {"sha": HEAD},
                    "base": {
                        "sha": BASE,
                        "repo": {"id": 123, "full_name": "TakashiSasaki/templates"},
                    },
                }
            ]
        )

    provider = OBSERVE.GhReadonlyProvider(api)
    observed = provider.read_binding(live_candidate, budget=unlimited_budget())
    snapshot = OBSERVE.build_snapshot(
        candidate=live_candidate,
        observed_start=observed,
        observed_end=observed,
        surfaces={"comments": surface([])},
        requested_surfaces=["comments"],
        observation={"provider": "fake"},
    )

    assert snapshot["binding_status"] == "stale"
    assert "start_provider_identity_does_not_match_expected" in snapshot[
        "binding_reasons"
    ]


@pytest.mark.parametrize(
    ("candidate_kwargs", "binding_kwargs", "reason"),
    [
        (
            {"resource_id": OTHER_RESOURCE_ID},
            {},
            "provider_identity_does_not_match_expected",
        ),
        (
            {"repository_id": OTHER_REPOSITORY_ID},
            {},
            "provider_identity_does_not_match_expected",
        ),
        (
            {},
            {"repository_id": OTHER_REPOSITORY_ID},
            "provider_identity_does_not_match_expected",
        ),
    ],
)
def test_live_provider_identity_mismatch_is_stale(
    tmp_path: Path,
    candidate_kwargs: dict[str, str],
    binding_kwargs: dict[str, str],
    reason: str,
) -> None:
    provider = FakeProvider(
        [binding(**binding_kwargs), binding(**binding_kwargs)],
        {"comments": [surface([{"identity": "comment-1", "body": "data"}])]},
    )
    request_value = request(
        tmp_path,
    )
    request_value = OBSERVE.ObservationRequest(
        candidates=(candidate(**candidate_kwargs),),
        surfaces=request_value.surfaces,
        mode=request_value.mode,
        deadline=request_value.deadline,
        max_attempts=request_value.max_attempts,
        summary_limit=request_value.summary_limit,
        snapshot_path=request_value.snapshot_path,
        previous_snapshot_path=request_value.previous_snapshot_path,
    )

    result = run_observation(tmp_path, provider, observation_request=request_value)

    assert result["outcome"] == "stale"
    assert any(reason in item for item in result["snapshots"]["PR_node_123"]["binding_reasons"])


def test_dependency_identity_mismatch_is_stale_even_when_head_matches(tmp_path: Path) -> None:
    dependency = {
        "id": "policy-pr-1",
        "authority": "policy",
        "expected_head_sha": HEAD,
        "provider_identity": {
            "provider": "github",
            "repository_id": REPOSITORY_ID,
            "resource_id": "expected-dependency",
        },
        "provider_path": "/repos/TakashiSasaki/templates/pulls/1",
    }
    observed_dependency = {
        "id": "policy-pr-1",
        "head_sha": HEAD,
        "provider_identity": {
            "provider": "github",
            "repository_id": REPOSITORY_ID,
            "resource_id": "another-dependency",
        },
    }
    provider = FakeProvider(
        [binding(dependencies=[observed_dependency])] * 2,
        {"comments": [surface([])]},
    )
    result = run_observation(
        tmp_path,
        provider,
        observation_request=OBSERVE.ObservationRequest(
            candidates=(candidate(dependencies=[dependency]),),
            surfaces=("comments",),
            mode="single-shot",
            deadline=None,
            max_attempts=1,
            summary_limit=2,
            snapshot_path=tmp_path / "observation.json",
            previous_snapshot_path=None,
        ),
    )

    assert result["outcome"] == "stale"
    assert any(
        "dependency_provider_identity_mismatch" in reason
        for reason in result["snapshots"]["PR_node_123"]["binding_reasons"]
    )


def test_provider_identity_movement_between_captures_is_stale(tmp_path: Path) -> None:
    provider = FakeProvider(
        [
            binding(resource_id=RESOURCE_ID),
            binding(resource_id=OTHER_RESOURCE_ID),
        ],
        {"comments": [surface([])]},
    )

    result = run_observation(tmp_path, provider)

    assert result["outcome"] == "stale"
    assert "candidate_provider_identity_changed_during_observation" in result["snapshots"][
        "PR_node_123"
    ]["binding_reasons"]


@pytest.mark.parametrize(
    "first_state", ["changed", "stale", "incomplete", "unknown", "provider_failed"]
)
def test_single_shot_observes_every_candidate_after_first_non_normal_state(
    tmp_path: Path, first_state: str
) -> None:
    observation_request = two_candidate_request(tmp_path)
    if first_state == "changed":
        run_observation(
            tmp_path,
            FakeProvider(
                [binding()] * 4,
                {"comments": [surface([{"identity": "old"}]), surface([])]},
            ),
            observation_request=observation_request,
        )
        observation_request = two_candidate_request(
            tmp_path, previous=tmp_path / "observation.json"
        )
        provider = FakeProvider(
            [binding()] * 4,
            {"comments": [surface([{"identity": "new"}]), surface([])]},
        )
    elif first_state == "stale":
        provider = FakeProvider(
            [
                binding(head=OTHER_HEAD),
                binding(head=OTHER_HEAD),
                binding(),
                binding(),
            ],
            {"comments": [surface([]), surface([])]},
        )
    elif first_state == "incomplete":
        provider = FakeProvider(
            [binding()] * 4,
            {
                "comments": [
                    OBSERVE.ProviderFailure("incomplete", "page 2 failed"),
                    surface([]),
                ]
            },
        )
    else:
        provider = FakeProvider(
            [
                OBSERVE.ProviderFailure(
                    "permission" if first_state == "unknown" else "provider",
                    "provider failed",
                ),
                binding(),
                binding(),
            ],
            {"comments": [surface([])]},
        )

    result = run_observation(
        tmp_path,
        provider,
        observation_request=observation_request,
    )

    assert [item["candidate_id"] for item in result["candidates"]] == [
        "PR_node_123",
        "PR_node_456",
    ]
    assert result["coverage"]["omitted_candidate_ids"] == []
    assert result["coverage"]["aggregate"] == "complete"
    expected_outcome = first_state if first_state in {
        "changed",
        "stale",
        "incomplete",
    } else "unknown"
    assert result["candidates"][0]["outcome"] == expected_outcome


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

    assert result["outcome"] == "attempts_exhausted"
    assert result["termination"] == "attempts_exhausted"
    assert clock.sleeps == [1.0]
    assert result["resume"]["last_attempt"] == 2


def test_deadline_during_capture_stops_surfaces_and_omits_suffix_candidates(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    provider = FakeProvider(
        [binding()],
        {
            "comments": [surface([])],
            "reviews": [surface([])],
        },
        clock=clock,
        advance_on_surface=2.0,
    )
    observation_request = OBSERVE.ObservationRequest(
        candidates=(candidate(), candidate(identifier="PR_node_456")),
        surfaces=("comments", "reviews"),
        mode="single-shot",
        deadline=1.0,
        max_attempts=1,
        summary_limit=2,
        snapshot_path=tmp_path / "observation.json",
        previous_snapshot_path=None,
    )

    result = run_observation(
        tmp_path,
        provider,
        observation_request=observation_request,
        clock=clock,
    )

    assert result["outcome"] == "deadline_reached"
    assert result["termination"] == "deadline"
    assert provider.surface_calls == [("PR_node_123", "comments")]
    assert result["coverage"]["omitted_candidate_ids"] == ["PR_node_456"]
    assert result["coverage"]["aggregate"] == "partial"
    assert result["candidates"][-1]["omitted"] is True
    assert json.loads((tmp_path / "observation.json").read_text())["outcome"] == (
        "deadline_reached"
    )


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


def test_keyboard_interrupt_during_provider_call_writes_cancelled_artifact(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [binding(), binding()],
        {"comments": [KeyboardInterrupt()]},
    )

    result = run_observation(tmp_path, provider)

    assert result["outcome"] == "cancelled"
    assert result["termination"] == "cancelled"
    assert result["candidates"][0]["error"]["category"] == "cancelled"
    assert json.loads((tmp_path / "observation.json").read_text())["outcome"] == (
        "cancelled"
    )


def test_request_rejects_duplicate_provider_candidate_identity_and_bad_surfaces(
    tmp_path: Path,
) -> None:
    base_request = {
        "schema_version": 1,
        "repository": "TakashiSasaki/templates",
        "candidates": [candidate().as_dict()],
        "surfaces": ["comments"],
        "max_attempts": 1,
        "snapshot_path": str(tmp_path / "observation.json"),
    }
    with pytest.raises(OBSERVE.ObservationInputError, match="provider identities"):
        OBSERVE.ObservationRequest.from_mapping(
            {
                **base_request,
                "candidates": [
                    candidate().as_dict(),
                    candidate(identifier="alias").as_dict(),
                ],
            }
        )
    with pytest.raises(OBSERVE.ObservationInputError, match="non-empty strings"):
        OBSERVE.ObservationRequest.from_mapping(
            {**base_request, "surfaces": ["comments", 1]}
        )


def test_deadline_limited_transport_timeout_is_deadline_not_generic_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout_run(*args: object, **kwargs: object) -> object:
        del args
        raise subprocess.TimeoutExpired(
            ["gh"], float(kwargs["timeout"])
        )

    monkeypatch.setattr(OBSERVE.subprocess, "run", timeout_run)
    budget = OBSERVE.ObservationBudget(1.0, clock=lambda: 0.0)

    with pytest.raises(OBSERVE.ProviderFailure) as raised:
        OBSERVE.gh_api_json(("/repos/TakashiSasaki/templates/pulls/1",), budget=budget)

    assert raised.value.category == "deadline"


def test_http_status_parser_ignores_json_body_text() -> None:
    assert OBSERVE._parse_http_metadata('{"message":"HTTP/1.1 403"}') == (
        None,
        None,
    )
    assert OBSERVE._parse_http_metadata(
        "HTTP/2 429\nretry-after: 2\n\n{}", now=lambda: 10.0
    ) == (429, 12.0)


def test_snapshot_path_validation_uses_repository_root_not_process_cwd() -> None:
    repository_root = OBSERVE.SCRIPT_DIR.parents[2].resolve()
    inside_repository = repository_root / "tests" / "inside-observation.json"

    with pytest.raises(OBSERVE.ObservationInputError, match="outside the repository"):
        OBSERVE._ensure_external_path(inside_repository, repository_root)


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
                            "node_id": "CR_1",
                            "name": "same-workflow",
                            "head_sha": HEAD,
                            "workflow_id": 11,
                            "run_id": 22,
                            "run_attempt": 3,
                            "job_id": 33,
                            "status": "completed",
                            "conclusion": "success",
                            "app": {"id": 7, "slug": "actions"},
                        },
                        {
                            "id": 2,
                            "node_id": "CR_2",
                            "name": "same-workflow",
                            "head_sha": HEAD,
                            "status": "completed",
                            "conclusion": "failure",
                        },
                    ]
                }
            ]
        ),
        "status": OBSERVE.ApiResponse(
            [
                {
                    "statuses": [
                        {
                            "id": 101,
                            "context": "same-workflow",
                            "target_url": "https://example.test/check",
                            "state": "success",
                        },
                        {
                            "id": 102,
                            "context": "same-workflow",
                            "target_url": "https://example.test/check",
                            "state": "failure",
                        },
                    ]
                }
            ]
        ),
    }

    def api(arguments: tuple[str, ...], **_: object) -> OBSERVE.ApiResponse:
        endpoint = arguments[-1]
        for key, response in responses.items():
            if key in endpoint:
                return response
        raise AssertionError(arguments)

    provider = OBSERVE.GhReadonlyProvider(api)
    result = provider._checks(candidate_value, HEAD, budget=unlimited_budget())

    assert len(result["records"]) == 4
    assert {record["identity"] for record in result["records"]} == {
        "check-run:1",
        "check-run:2",
        "status:101",
        "status:102",
    }
    assert {
        record["conclusion"]
        for record in result["records"]
        if record["provider_kind"] == "check_run"
    } == {
        "success",
        "failure",
    }
    assert result["records"][0]["observed_head_sha"] == HEAD
    assert result["records"][0]["head_sha"] == HEAD
    assert result["records"][0]["workflow_id"] == 11
    assert result["records"][0]["run_id"] == 22
    assert result["records"][0]["run_attempt"] == 3
    assert result["records"][0]["job_id"] == 33
    assert result["records"][0]["app"]["id"] == 7


def test_transport_timeout_never_exceeds_remaining_budget() -> None:
    clock = FakeClock(now=3.0)
    budget = OBSERVE.ObservationBudget(10.0, clock=clock)
    timeouts: list[float] = []
    passed_budgets: list[OBSERVE.ObservationBudget] = []

    def api(
        arguments: tuple[str, ...],
        *,
        timeout: float,
        budget: OBSERVE.ObservationBudget,
        **_: object,
    ) -> OBSERVE.ApiResponse:
        timeouts.append(timeout)
        passed_budgets.append(budget)
        endpoint = arguments[-1]
        if endpoint.endswith("check-runs"):
            return OBSERVE.ApiResponse([{"check_runs": []}])
        if endpoint.endswith("/status"):
            return OBSERVE.ApiResponse([{"statuses": []}])
        raise AssertionError(arguments)

    provider = OBSERVE.GhReadonlyProvider(api)
    provider._checks(candidate(), HEAD, budget=budget)

    assert timeouts == [7.0, 7.0]
    assert all(timeout <= 7.0 for timeout in timeouts)
    assert passed_budgets == [budget, budget]


def test_adapter_passes_budget_to_transport_deadline_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock(now=0.0)
    budget = OBSERVE.ObservationBudget(1.0, clock=clock)
    passed_budgets: list[OBSERVE.ObservationBudget] = []

    def timeout_run(command: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(command, float(kwargs["timeout"]))

    monkeypatch.setattr(OBSERVE.subprocess, "run", timeout_run)

    def api(
        arguments: tuple[str, ...],
        *,
        timeout: float,
        budget: OBSERVE.ObservationBudget,
    ) -> OBSERVE.ApiResponse:
        passed_budgets.append(budget)
        return OBSERVE.gh_api_json(arguments, timeout=timeout, budget=budget)

    with pytest.raises(OBSERVE.ProviderFailure) as raised:
        OBSERVE.GhReadonlyProvider(api)._checks(
            candidate(), HEAD, budget=budget
        )

    assert raised.value.category == "deadline"
    assert passed_budgets == [budget]


def test_reactions_cover_pr_issue_and_comment_surfaces() -> None:
    calls: list[tuple[str, ...]] = []

    def api(arguments: tuple[str, ...], **_: object) -> OBSERVE.ApiResponse:
        calls.append(arguments)
        endpoint = arguments[-1]
        if endpoint.endswith("/issues/123/comments"):
            return OBSERVE.ApiResponse([[{"id": 11}]])
        if endpoint.endswith("/pulls/123/comments"):
            return OBSERVE.ApiResponse(
                [
                    [
                        {
                            "id": 22,
                            "body": "inline finding",
                            "commit_id": HEAD,
                            "original_commit_id": BASE,
                            "pull_request_review_id": 77,
                        }
                    ]
                ]
            )
        if endpoint.endswith("/issues/123/reactions"):
            return OBSERVE.ApiResponse([[{"id": 1, "content": "+1"}]])
        if endpoint.endswith("/issues/comments/11/reactions"):
            return OBSERVE.ApiResponse([[{"id": 2, "content": "heart"}]])
        if endpoint.endswith("/pulls/comments/22/reactions"):
            return OBSERVE.ApiResponse([[{"id": 3, "content": "rocket"}]])
        raise AssertionError(arguments)

    provider = OBSERVE.GhReadonlyProvider(api)
    result = provider._reactions(candidate(), budget=unlimited_budget())

    assert result["complete"] is True
    assert {
        record["identity"] for record in result["records"]
    } == {
        "review-comment:22",
        "pull_request:123:reaction:1",
        "issue_comment:11:reaction:2",
        "review_comment:22:reaction:3",
    }
    review_comment = next(
        record for record in result["records"] if record["identity"] == "review-comment:22"
    )
    assert review_comment["commit_id"] == HEAD
    assert review_comment["original_commit_id"] == BASE
    assert review_comment["pull_request_review_id"] == 77
    assert all("--paginate" in call for call in calls)


def test_review_thread_comments_paginate_past_one_hundred() -> None:
    first_comments = [
        {"id": f"comment-{index}", "body": f"body-{index}"}
        for index in range(100)
    ]
    calls: list[tuple[str, ...]] = []

    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        calls.append(arguments)
        if any(argument == "threadId=thread-1" for argument in arguments):
            return OBSERVE.ApiResponse(
                {
                    "data": {
                        "node": {
                            "comments": {
                                "nodes": [{"id": "comment-100", "body": "body-100"}],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            )
        return OBSERVE.ApiResponse(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "id": "thread-1",
                                        "isResolved": False,
                                        "comments": {
                                            "nodes": first_comments,
                                            "pageInfo": {
                                                "hasNextPage": True,
                                                "endCursor": "comment-cursor-1",
                                            },
                                        },
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            }
        )

    provider = OBSERVE.GhReadonlyProvider(api)
    result = provider._threads(candidate(), budget=unlimited_budget())

    assert result["complete"] is True
    assert len(result["records"][0]["comments"]["nodes"]) == 101
    assert len(calls) == 2
    assert any(argument == "threadId=thread-1" for argument in calls[1])


@pytest.mark.parametrize("case", ["missing", "duplicate"])
def test_review_thread_comments_require_stable_unique_ids(case: str) -> None:
    initial_comments = [{"body": "missing"}] if case == "missing" else [{"id": "comment-1"}]

    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        if case == "duplicate" and any(
            argument == "threadId=thread-1" for argument in arguments
        ):
            return OBSERVE.ApiResponse(
                {
                    "data": {
                        "node": {
                            "comments": {
                                "nodes": [{"id": "comment-1"}],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            }
                        }
                    }
                }
            )
        return OBSERVE.ApiResponse(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "id": "thread-1",
                                        "comments": {
                                            "nodes": initial_comments,
                                            "pageInfo": {
                                                "hasNextPage": case == "duplicate",
                                                "endCursor": (
                                                    "comment-cursor-1"
                                                    if case == "duplicate"
                                                    else None
                                                ),
                                            },
                                        },
                                    }
                                ],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            }
                        }
                    }
                }
            }
        )

    provider = OBSERVE.GhReadonlyProvider(api)
    with pytest.raises(OBSERVE.ProviderFailure, match="stable id|duplicate"):
        provider._threads(candidate(), budget=unlimited_budget())


def test_review_thread_outer_cursor_must_advance() -> None:
    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        repeated = any(argument == "after=outer-cursor-1" for argument in arguments)
        return OBSERVE.ApiResponse(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": "outer-cursor-1",
                                },
                            }
                        }
                    }
                }
            }
            if repeated
            else {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "id": "thread-1",
                                        "comments": {
                                            "nodes": [],
                                            "pageInfo": {
                                                "hasNextPage": False,
                                                "endCursor": None,
                                            },
                                        },
                                    }
                                ],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": "outer-cursor-1",
                                },
                            }
                        }
                    }
                }
            }
        )

    with pytest.raises(OBSERVE.ProviderFailure, match="cursor did not advance"):
        OBSERVE.GhReadonlyProvider(api)._threads(candidate(), budget=unlimited_budget())


def test_review_thread_nested_cursor_must_advance() -> None:
    def api(
        arguments: tuple[str, ...], *, timeout: float, **_: object
    ) -> OBSERVE.ApiResponse:
        del timeout
        repeated = any(
            argument == "after=comment-cursor-1" for argument in arguments
        )
        if repeated:
            return OBSERVE.ApiResponse(
                {
                    "data": {
                        "node": {
                            "comments": {
                                "nodes": [],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": "comment-cursor-1",
                                },
                            }
                        }
                    }
                }
            )
        return OBSERVE.ApiResponse(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "id": "thread-1",
                                        "comments": {
                                            "nodes": [{"id": "comment-1"}],
                                            "pageInfo": {
                                                "hasNextPage": True,
                                                "endCursor": "comment-cursor-1",
                                            },
                                        },
                                    }
                                ],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            }
                        }
                    }
                }
            }
        )

    with pytest.raises(OBSERVE.ProviderFailure, match="cursor did not advance"):
        OBSERVE.GhReadonlyProvider(api)._threads(candidate(), budget=unlimited_budget())


def test_bounded_summary_caps_many_candidates_and_declares_omissions() -> None:
    candidates = [
        {
            "candidate_id": f"candidate-{index}",
            "outcome": "changed",
            "attempted": True,
            "omitted": False,
            "diff": {
                "status": "changed",
                "meaningful_change": True,
                "counts": {"added": 100},
                "changes": [
                    {
                        "surface": "comments",
                        "kind": "added",
                        "identity": f"comment-{index}",
                        "record": {"body": "x" * 100_000},
                    }
                ]
                * 10,
                "unknowns": [],
            },
        }
        for index in range(400)
    ]
    result = {
        "kind": "pr-state-observation-result",
        "outcome": "changed",
        "termination": "completed",
        "attempts": 1,
        "candidates": candidates,
        "coverage": {
            "requested_candidate_ids": [item["candidate_id"] for item in candidates],
            "attempted_candidate_ids": [item["candidate_id"] for item in candidates],
            "acquired_candidate_ids": [],
            "omitted_candidate_ids": [],
            "all_requested_attempted": True,
            "aggregate": "complete",
        },
        "snapshot_reference": {"path": "/tmp/detail.json", "digest": "a" * 64},
        "resume": {"reason": "changed"},
    }

    summary = OBSERVE.bounded_summary(result, 20)

    assert len(
        json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ) <= (
        OBSERVE.MODEL_SUMMARY_MAX_BYTES
    )
    assert summary["summary_truncated"] is True
    assert summary["candidate_id_digest"]
    assert summary["omitted_candidate_count"] > 0


def test_bounded_summary_compacts_large_omitted_candidate_coverage() -> None:
    omitted_ids = [f"candidate-{index}" for index in range(1000)]
    summary = OBSERVE.bounded_summary(
        {
            "kind": "pr-state-observation-result",
            "outcome": "deadline_reached",
            "termination": "deadline",
            "attempts": 1,
            "candidates": [],
            "coverage": {
                "requested_candidate_ids": omitted_ids,
                "attempted_candidate_ids": [],
                "acquired_candidate_ids": [],
                "omitted_candidate_ids": omitted_ids,
                "all_requested_attempted": False,
                "aggregate": "partial",
            },
            "snapshot_reference": {"path": "/tmp/detail.json", "digest": "a" * 64},
            "resume": {"reason": "deadline_reached"},
        },
        2,
    )

    encoded = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    assert len(encoded) <= OBSERVE.MODEL_SUMMARY_MAX_BYTES
    assert summary["coverage"]["omitted_candidate_count"] == 1000
    assert summary["coverage"]["omitted_candidate_ids_truncated"] is True
    assert len(summary["coverage"]["omitted_candidate_ids"]) == 16
    assert summary["coverage"]["omitted_candidate_id_digest"]


def test_write_methods_and_malformed_responses_fail_closed() -> None:
    with pytest.raises(OBSERVE.ObservationInputError, match="write methods"):
        OBSERVE.gh_api_json(("POST", "/repos/TakashiSasaki/templates/pulls/1"))

    def malformed(_: tuple[str, ...], **__: object) -> OBSERVE.ApiResponse:
        return OBSERVE.ApiResponse({"not": "a pull request"})

    provider = OBSERVE.GhReadonlyProvider(malformed)
    with pytest.raises(OBSERVE.ProviderFailure, match="pull request head"):
        provider.read_binding(candidate(), budget=unlimited_budget())


def test_paginated_http_bodies_are_decoded_without_slurp_flag() -> None:
    bodies = OBSERVE._decode_json_bodies(
        "HTTP/2 200\ncontent-type: application/json\n\n"
        "{\"page\": 1}\n"
        "HTTP/2 200\ncontent-type: application/json\n\n"
        "{\"page\": 2}\n"
    )

    assert bodies == [{"page": 1}, {"page": 2}]
