from __future__ import annotations

import base64
import copy
import hashlib
import http.client
import importlib.util
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER_PATH = (
    ROOT / "repository-skills" / "land-templates-stack" / "scripts" / "publish_review_artifacts.py"
)
SOURCE_FIXTURE_PATH = ROOT / "tests" / "test_review_artifacts.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = _load_module(PUBLISHER_PATH, "publish_review_artifacts")
source_fixture = _load_module(SOURCE_FIXTURE_PATH, "review_artifact_source_fixture")


def _bound_source(body: str = "Human PR text\n", *, with_region: bool = False):
    source = source_fixture._source()
    source["observed"]["pr_body"] = {"revision": "body-1", "body": body}
    normalized = publisher.renderer.normalize(source)
    if with_region:
        region = publisher.renderer.render(normalized).files["pr-generated-region.md"]
        source["observed"]["pr_body"]["body"] = body + region
        normalized = publisher.renderer.normalize(source)
    return normalized


class FakeProvider(publisher.RemoteProvider):
    def __init__(self, normalized, *, body: str | None = None) -> None:
        self.normalized = normalized
        initial_body = normalized.data["observed"]["pr_body"]["body"] if body is None else body
        self.state = {
            **publisher._expected_binding(normalized),
            "body": initial_body,
            "body_revision": normalized.data["observed"]["pr_body"]["revision"],
            "body_digest": publisher.renderer.semantic_digest(initial_body),
        }
        self.comments: list[dict[str, object]] = []
        self.get_calls = 0
        self.list_calls = 0
        self.update_calls = 0
        self.create_calls = 0
        self.mutate_before_update = False
        self.ambiguous_body = False
        self.ambiguous_comment = False
        self.apply_ambiguous_comment = False

    def get_current_state(
        self,
        repository: str,
        number: int,
        *,
        context=None,
    ) -> dict[str, object]:
        assert context is self.normalized
        self.get_calls += 1
        if self.mutate_before_update and self.get_calls == 2:
            self._set_body("Concurrent human edit\n")
        return copy.deepcopy(self.state)

    def list_comments(self, repository: str, number: int) -> list[dict[str, object]]:
        self.list_calls += 1
        return copy.deepcopy(self.comments)

    def update_pr_body(self, repository: str, number: int, body: str):
        self.update_calls += 1
        self._set_body(body)
        if self.ambiguous_body:
            raise publisher.RemoteAmbiguousError("body response lost")
        return {"body": body}

    def create_comment(self, repository: str, number: int, body: str):
        self.create_calls += 1
        if not self.ambiguous_comment or self.apply_ambiguous_comment:
            self.comments.append({"id": self.create_calls, "body": body})
        if self.ambiguous_comment:
            raise publisher.RemoteAmbiguousError("comment response lost")
        return {"id": self.create_calls, "body": body}

    def _set_body(self, body: str) -> None:
        self.state["body"] = body
        self.state["body_revision"] = publisher.renderer.semantic_digest(body)
        self.state["body_digest"] = publisher.renderer.semantic_digest(body)


def _publish(provider: FakeProvider, *, initialize: bool = True):
    return publisher.publish(
        provider.normalized,
        provider,
        apply=True,
        authorized=True,
        serialized_writer=True,
        initialize_region=initialize,
    )


def test_preview_is_side_effect_free_and_does_not_read_remote_state() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)

    result = publisher.publish(normalized, provider)

    assert result.status == "preview"
    assert provider.get_calls == 0
    assert provider.list_calls == 0
    assert provider.update_calls == 0
    assert provider.create_calls == 0


def test_apply_requires_both_explicit_authorization_and_serialized_writer() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)

    unauthorized = publisher.publish(normalized, provider, apply=True)
    assert unauthorized.status == "needs_authorization"
    assert provider.get_calls == 0

    no_writer = publisher.publish(normalized, provider, apply=True, authorized=True)
    assert no_writer.status == "needs_serialized_writer"
    assert provider.get_calls == 0


def test_publish_updates_owned_body_and_creates_one_request_and_checkpoint() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)

    result = _publish(provider)

    assert result.status == "published"
    assert provider.update_calls == 1
    assert provider.create_calls == 2
    assert provider.state["body"].startswith("Human PR text\n")
    assert provider.state["body"].count(publisher.renderer.GENERATED_REGION_START) == 1
    assert len(provider.comments) == 2

    repeated = _publish(provider)
    assert repeated.status == "published"
    assert provider.update_calls == 1
    assert provider.create_calls == 2
    assert all(
        item["status"] == "already_present"
        for item in repeated.operations
        if item["type"] != "update_pr_body"
    )


def test_stale_head_dependency_or_planner_binding_stops_before_any_write() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)
    provider.state["head_sha"] = "9" * 40
    provider.state["candidate_head_sha"] = "9" * 40

    result = _publish(provider)

    assert result.status == "stale"
    assert "current_head_sha_changed" in result.reasons
    assert provider.update_calls == 0
    assert provider.create_calls == 0


def test_stale_base_or_existing_evaluation_binding_stops_before_any_write() -> None:
    for field, value in (
        ("base_sha", "8" * 40),
        ("effective_base_sha", "8" * 40),
        ("planner_input_digest", "8" * 64),
        ("planner_result_digest", "8" * 64),
        ("gate_input_binding_digest", "8" * 64),
    ):
        normalized = _bound_source()
        provider = FakeProvider(normalized)
        provider.state[field] = value

        result = _publish(provider)

        assert result.status == "stale"
        assert any(field in reason for reason in result.reasons)
        assert provider.update_calls == 0
        assert provider.create_calls == 0


def test_gate_status_or_evidence_change_stops_before_any_write() -> None:
    for field, value in (("gate_status", "failed"), ("evidence_digest", "8" * 64)):
        normalized = _bound_source()
        provider = FakeProvider(normalized)
        provider.state[field] = value

        result = _publish(provider)

        assert result.status == "stale"
        assert any(field in reason for reason in result.reasons)
        assert provider.update_calls == 0
        assert provider.create_calls == 0


def test_body_conflict_between_read_and_write_is_not_overwritten() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)
    provider.mutate_before_update = True

    result = _publish(provider)

    assert result.status == "conflict"
    assert provider.update_calls == 0
    assert provider.state["body"] == "Concurrent human edit\n"


def test_missing_or_duplicated_markers_fail_closed_without_body_replacement() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)

    missing = _publish(provider, initialize=False)
    assert missing.status == "conflict"
    assert provider.update_calls == 0

    existing = _bound_source(with_region=True)
    duplicate_body = (
        existing.data["observed"]["pr_body"]["body"]
        + publisher.renderer.GENERATED_REGION_START
        + "\n"
        + publisher.renderer.GENERATED_REGION_END
    )
    duplicate_provider = FakeProvider(existing, body=duplicate_body)
    duplicate = _publish(duplicate_provider, initialize=False)
    assert duplicate.status == "conflict"
    assert duplicate_provider.update_calls == 0


def test_equivalent_request_marker_is_reused_without_duplicate_post() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)
    key = publisher.renderer.idempotency_key(normalized, "review-request")
    provider.comments.append(
        {"id": 1, "body": f"<!-- {publisher.renderer.REVIEW_REQUEST_MARKER}:key={key} -->"}
    )

    result = _publish(provider)

    assert result.status == "published"
    assert provider.create_calls == 1
    review_operations = [item for item in result.operations if item["type"] == "review_request"]
    assert review_operations[0]["status"] == "already_present"


def test_lost_comment_response_is_reconciled_or_reported_ambiguous_without_retry() -> None:
    normalized = _bound_source()
    applied = FakeProvider(normalized)
    applied.ambiguous_comment = True
    applied.apply_ambiguous_comment = True

    reconciled = _publish(applied)

    assert reconciled.status == "published"
    assert applied.create_calls == 2
    request_key = publisher.renderer.idempotency_key(normalized, "review-request")
    request_comments = [
        item for item in applied.comments if f"key={request_key}" in str(item["body"])
    ]
    assert len(request_comments) == 1
    assert any(item.get("status") == "reconciled" for item in reconciled.operations)

    not_applied = FakeProvider(normalized)
    not_applied.ambiguous_comment = True
    ambiguous = _publish(not_applied)

    assert ambiguous.status == "ambiguous"
    assert not_applied.create_calls == 1
    assert len(not_applied.comments) == 0


def test_lost_body_response_is_reconciled_when_body_is_observed_as_applied() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)
    provider.ambiguous_body = True

    result = _publish(provider)

    assert result.status == "published"
    assert provider.update_calls == 1
    assert any(item.get("status") == "reconciled" for item in result.operations)


def test_partial_observation_does_not_publish_a_new_review_request() -> None:
    source = source_fixture._source()
    source["observed"]["complete"] = False
    source["observed"]["pr_body"] = {"revision": "body-1", "body": "Human PR text\n"}
    normalized = publisher.renderer.normalize(source)
    provider = FakeProvider(normalized)

    result = _publish(provider)

    assert result.status == "published"
    request_operations = [item for item in result.operations if item["type"] == "review_request"]
    assert request_operations[0]["status"] == "observation_handoff"
    assert provider.create_calls == 1


def test_missing_live_dependency_binding_is_stale_even_when_pr_identity_matches() -> None:
    normalized = _bound_source()
    provider = FakeProvider(normalized)
    del provider.state["revision_bindings_digest"]

    result = _publish(provider)

    assert result.status == "stale"
    assert "current_revision_bindings_digest_not_observed" in result.reasons
    assert provider.update_calls == 0


def test_publisher_reuses_existing_rendered_region_without_churn() -> None:
    normalized = _bound_source(with_region=True)
    provider = FakeProvider(normalized)

    result = _publish(provider, initialize=False)

    assert result.status == "published"
    assert provider.update_calls == 0
    assert provider.create_calls == 2


def test_preview_request_is_provider_neutral_but_github_apply_has_codex_trigger() -> None:
    normalized = _bound_source()
    assert "@codex review" not in publisher.renderer.render(normalized).files["review-request.md"]

    class RecordingGitHub(publisher.GitHubProvider):
        def __init__(self) -> None:
            super().__init__("token")
            self.payloads: list[dict[str, object]] = []

        def _request(self, method, path, payload=None):
            self.payloads.append({"method": method, "path": path, "payload": payload})
            return {"id": 55, "body": payload["body"]}

    provider = RecordingGitHub()
    body = publisher.renderer.render(normalized).files["review-request.md"]
    normalized.data["candidate"]["members"][0]["pull_request"] = {
        "number": 123,
    }
    result = provider.create_review_request(
        "TakashiSasaki/templates", 123, body, context=normalized
    )

    assert result["id"] == 55
    posted = provider.payloads[0]["payload"]["body"]
    assert posted.startswith("@codex review\n\n")
    assert publisher.renderer.REVIEW_REQUEST_MARKER in posted
    assert "## Exact ordered stack topology" in posted
    assert "PR #123" in posted


def test_github_marker_without_trigger_does_not_suppress_a_new_codex_request() -> None:
    normalized = _bound_source()
    provider = publisher.GitHubProvider("token")
    current = {
        **publisher._expected_binding(normalized),
        "body": normalized.data["observed"]["pr_body"]["body"],
        "body_revision": normalized.data["observed"]["pr_body"]["revision"],
        "body_digest": publisher.renderer.semantic_digest(
            normalized.data["observed"]["pr_body"]["body"]
        ),
    }
    key = publisher.renderer.idempotency_key(normalized, "review-request")
    operations, _ = publisher._planned_operations(
        normalized,
        provider,
        current,
        [{"body": f"<!-- {publisher.renderer.REVIEW_REQUEST_MARKER}:key={key} -->"}],
        initialize=True,
    )
    review = next(item for item in operations if item["type"] == "review_request")
    assert review["status"] == "create"


def test_reuse_planner_action_does_not_emit_a_new_review_operation() -> None:
    normalized = _bound_source()
    normalized.data["planner"]["result"]["action"] = "reuse_existing_result"
    normalized.planner_result["action"] = "reuse_existing_result"
    provider = FakeProvider(normalized)

    result = _publish(provider)

    review = next(item for item in result.operations if item["type"] == "review_request")
    assert review["status"] == "planner_reuse"
    assert provider.create_calls == 1


def test_checkpoint_identity_changes_with_resume_state_but_not_review_identity() -> None:
    first = _bound_source()
    changed_source = source_fixture._source()
    changed_source["observed"]["pr_body"] = {
        "revision": "body-1",
        "body": "Human PR text\n",
    }
    changed_source["work"]["blockers"] = ["dependency-review-pending"]
    changed = publisher.renderer.normalize(changed_source)

    assert publisher.renderer.checkpoint_identity(first) != publisher.renderer.checkpoint_identity(
        changed
    )
    assert publisher.renderer.idempotency_key(
        first, "review-request"
    ) == publisher.renderer.idempotency_key(changed, "review-request")

    provider = FakeProvider(changed)
    provider.comments.append(
        {
            "id": 1,
            "body": publisher.renderer.render(first).files["work-ledger-checkpoint.md"],
        }
    )
    operations, _ = publisher._planned_operations(
        changed,
        provider,
        provider.state,
        provider.comments,
        initialize=True,
    )
    checkpoint = next(item for item in operations if item["type"] == "work_checkpoint")
    assert checkpoint["status"] == "create"


def test_live_observation_rejects_ambiguous_or_unobserved_stack_members() -> None:
    normalized = _bound_source()
    payload = {
        "id": 123,
        "number": 123,
        "base": {
            "sha": normalized.data["candidate"]["base_sha"],
            "repo": {"id": 9, "full_name": normalized.data["repository"]},
        },
        "head": {"sha": normalized.data["candidate"]["head_sha"]},
    }
    observer = publisher._load_observer_entrypoint()

    duplicate = copy.deepcopy(normalized)
    duplicate.data["candidate"]["members"].append(
        copy.deepcopy(duplicate.data["candidate"]["members"][0])
    )
    duplicate.data["candidate"]["members"][1]["id"] = "duplicate-target"
    with pytest.raises(publisher.PublicationError, match="duplicate PR numbers"):
        publisher.GitHubLiveRevalidationAdapter._observation_candidate(
            duplicate, payload, observer
        )

    missing_target = copy.deepcopy(normalized)
    missing_target.data["candidate"]["members"][0]["pull_request"]["number"] = 124
    missing_target.data["candidate"]["members"][0]["pull_request"]["provider_identity"][
        "resource_id"
    ] = "124"
    missing_target.data["candidate"]["members"][0]["pull_request"][
        "provider_path"
    ] = "/repos/TakashiSasaki/templates/pulls/124"
    with pytest.raises(publisher.PublicationError, match="target PR exactly once"):
        publisher.GitHubLiveRevalidationAdapter._observation_candidate(
            missing_target, payload, observer
        )

    complete = copy.deepcopy(normalized)
    complete.data["candidate"]["members"].insert(
        0,
        {
            "id": "policy-prerequisite",
            "authority": "policy",
            "base_sha": normalized.data["candidate"]["base_sha"],
            "head_sha": normalized.data["candidate"]["base_sha"],
            "pull_request": {
                "number": 122,
                "provider_identity": {
                    "provider": "github",
                    "repository_id": "9",
                    "resource_id": "122",
                },
                "provider_path": "/repos/TakashiSasaki/templates/pulls/122",
            },
        },
    )
    binding = publisher.GitHubLiveRevalidationAdapter._observation_candidate(
        complete, payload, observer
    )
    assert [item.identifier for item in binding.dependencies] == ["policy-prerequisite"]
    assert binding.dependencies[0].expected_base_sha == normalized.data["candidate"]["base_sha"]


def _two_member_normalized_stack() -> tuple[object, str, str]:
    normalized = _bound_source()
    candidate = normalized.data["candidate"]
    lower_base = "d" * 40
    lower_head = candidate["base_sha"]
    candidate["members"].insert(
        0,
        {
            "id": "policy-prerequisite",
            "authority": "policy",
            "base_sha": lower_base,
            "head_sha": lower_head,
            "pull_request": {
                "number": 122,
                "provider_identity": {
                    "provider": "github",
                    "repository_id": "9",
                    "resource_id": "122",
                },
                "provider_path": "/repos/TakashiSasaki/templates/pulls/122",
            },
        },
    )
    return normalized, lower_base, lower_head


def test_dependency_base_binding_detects_base_only_movement() -> None:
    normalized, lower_base, lower_head = _two_member_normalized_stack()
    payload = {
        "id": 123,
        "number": 123,
        "base": {
            "sha": normalized.data["candidate"]["base_sha"],
            "repo": {"id": 9, "full_name": normalized.data["repository"]},
        },
        "head": {"sha": normalized.data["candidate"]["head_sha"]},
    }
    observer = publisher._load_observer_entrypoint()
    candidate_binding = publisher.GitHubLiveRevalidationAdapter._observation_candidate(
        normalized, payload, observer
    )
    dependency_identity = candidate_binding.dependencies[0].provider_identity.as_dict()
    start = {
        "provider_identity": candidate_binding.provider_identity.as_dict(),
        "head_sha": candidate_binding.expected_head_sha,
        "base_sha": candidate_binding.expected_base_sha,
        "dependencies": [
            {
                "id": "policy-prerequisite",
                "head_sha": lower_head,
                "base_sha": lower_base,
                "provider_identity": dependency_identity,
            }
        ],
    }
    end = copy.deepcopy(start)
    end["dependencies"][0]["base_sha"] = "e" * 40
    observation = publisher._load_observation_model()

    reasons = observation.binding_mismatch_reasons(candidate_binding, start, end)

    assert "end_dependency_base_changed:policy-prerequisite" in reasons


def test_live_stack_requires_adjacency_and_accepts_a_normal_restack() -> None:
    normalized, lower_base, lower_head = _two_member_normalized_stack()
    observer = publisher._load_observer_entrypoint()
    payload = {
        "id": 123,
        "number": 123,
        "base": {
            "sha": normalized.data["candidate"]["base_sha"],
            "repo": {"id": 9, "full_name": normalized.data["repository"]},
        },
        "head": {"sha": normalized.data["candidate"]["head_sha"]},
    }
    binding = publisher.GitHubLiveRevalidationAdapter._observation_candidate(
        normalized, payload, observer
    )
    assert binding.dependencies[0].expected_base_sha == lower_base

    restacked = copy.deepcopy(normalized)
    restacked.data["candidate"]["members"][0]["base_sha"] = "f" * 40
    restacked.data["candidate"]["members"][0]["head_sha"] = "e" * 40
    restacked.data["candidate"]["members"][1]["base_sha"] = "e" * 40
    restacked_payload = copy.deepcopy(payload)
    restacked_payload["base"]["sha"] = "e" * 40
    restacked_binding = publisher.GitHubLiveRevalidationAdapter._observation_candidate(
        restacked, restacked_payload, observer
    )
    assert restacked_binding.dependencies[0].expected_base_sha == "f" * 40

    broken = copy.deepcopy(restacked)
    broken.data["candidate"]["members"][1]["base_sha"] = "d" * 40
    broken_payload = copy.deepcopy(restacked_payload)
    broken_payload["base"]["sha"] = "d" * 40
    with pytest.raises(publisher.PublicationError, match="ordered base-to-head chain"):
        publisher.GitHubLiveRevalidationAdapter._observation_candidate(
            broken, broken_payload, observer
        )


def test_truncated_mutation_responses_are_ambiguous_for_body_and_comment(
    monkeypatch,
) -> None:
    class TruncatedResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            raise http.client.IncompleteRead(b"partial", 20)

    provider = publisher.GitHubProvider("token")
    calls: list[str] = []

    def urlopen(request, timeout):
        del timeout
        calls.append(request.method)
        return TruncatedResponse()

    monkeypatch.setattr(publisher.urllib.request, "urlopen", urlopen)
    with pytest.raises(publisher.RemoteAmbiguousError):
        provider.update_pr_body("TakashiSasaki/templates", 123, "body")
    with pytest.raises(publisher.RemoteAmbiguousError):
        provider.create_comment("TakashiSasaki/templates", 123, "comment")
    assert calls == ["PATCH", "POST"]


def test_truncated_http_error_bodies_reconcile_all_mutation_surfaces(
    monkeypatch,
) -> None:
    class TruncatedBody:
        def read(self, *args):
            del args
            raise http.client.IncompleteRead(b"partial", 20)

        def close(self):
            return None

    calls: list[str] = []

    def urlopen(request, timeout):
        del timeout
        calls.append(request.method)
        raise urllib.error.HTTPError(
            request.full_url,
            502,
            "upstream failure",
            {},
            TruncatedBody(),
        )

    monkeypatch.setattr(publisher.urllib.request, "urlopen", urlopen)
    provider = publisher.GitHubProvider("token")

    with pytest.raises(publisher.RemoteAmbiguousError):
        provider.update_pr_body("TakashiSasaki/templates", 123, "body")
    with pytest.raises(publisher.RemoteAmbiguousError):
        provider.create_review_request("TakashiSasaki/templates", 123, "request")
    with pytest.raises(publisher.RemoteAmbiguousError):
        provider.create_comment("TakashiSasaki/templates", 123, "checkpoint")
    with pytest.raises(publisher.PublicationError, match="error response could not be read"):
        provider._request("GET", "/repos/TakashiSasaki/templates/pulls/123")

    assert calls == ["PATCH", "POST", "POST", "GET"]


def test_complete_http_error_body_remains_a_deterministic_error(monkeypatch) -> None:
    class CompleteBody:
        def read(self, *args):
            del args
            return b'{"message":"validation failed"}'

        def close(self):
            return None

    def urlopen(request, timeout):
        del timeout
        raise urllib.error.HTTPError(
            request.full_url,
            422,
            "validation failed",
            {},
            CompleteBody(),
        )

    monkeypatch.setattr(publisher.urllib.request, "urlopen", urlopen)
    provider = publisher.GitHubProvider("token")

    with pytest.raises(publisher.PublicationError, match="returned 422") as error:
        provider.create_comment("TakashiSasaki/templates", 123, "comment")

    assert "validation failed" in str(error.value)


class _ContentGitHub(publisher.GitHubProvider):
    def __init__(self, payload):
        super().__init__("token")
        self.payload = payload

    def _request(self, method, path, payload=None):
        assert method == "GET"
        assert "/contents/.agent-policy.yml" in path
        return self.payload


def _content_payload(content: bytes, *, blob_sha: str | None = None) -> dict[str, object]:
    actual = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    return {
        "type": "file",
        "path": ".agent-policy.yml",
        "sha": actual if blob_sha is None else blob_sha,
        "encoding": "base64",
        "content": base64.b64encode(content).decode(),
    }


def test_live_consumer_pin_is_verified_from_exact_candidate_content() -> None:
    normalized = publisher.renderer.normalize(source_fixture._source())
    revision = normalized.data["revision_bindings"][0]["revision"]
    content = f"toolchain:\n  revision: {revision}\n".encode()
    provider = _ContentGitHub(_content_payload(content))

    publisher.GitHubLiveRevalidationAdapter._toolchain_revision(
        provider, normalized, normalized.data["candidate"]["head_sha"]
    )

    normalized.data["revision_bindings"][0]["revision"] = "d" * 40
    with pytest.raises(publisher.PublicationError, match="claim differs"):
        publisher.GitHubLiveRevalidationAdapter._toolchain_revision(
            provider, normalized, normalized.data["candidate"]["head_sha"]
        )


def test_live_consumer_pin_blob_mismatch_fails_closed() -> None:
    normalized = publisher.renderer.normalize(source_fixture._source())
    revision = normalized.data["revision_bindings"][0]["revision"]
    content = f"toolchain:\n  revision: {revision}\n".encode()
    provider = _ContentGitHub(_content_payload(content, blob_sha="f" * 40))

    with pytest.raises(publisher.PublicationError, match="blob identity"):
        publisher.GitHubLiveRevalidationAdapter._toolchain_revision(
            provider, normalized, normalized.data["candidate"]["head_sha"]
        )


class _LiveBoundaryGitHub(publisher.GitHubProvider):
    def __init__(self, normalized, live_revalidator):
        super().__init__("token", live_revalidator=live_revalidator)
        self.normalized = normalized
        self.body = normalized.data["observed"]["pr_body"]["body"]
        self.comments: list[dict[str, object]] = []
        self.writes = 0
        self.payload = {
            "id": 123,
            "node_id": normalized.data["candidate"]["pull_request"]["id"],
            "number": normalized.data["candidate"]["pull_request"]["number"],
            "body": self.body,
            "base": {
                "sha": normalized.data["candidate"]["base_sha"],
                "repo": {"id": 9, "full_name": normalized.data["repository"]},
            },
            "head": {"sha": normalized.data["candidate"]["head_sha"]},
        }

    def _request(self, method, path, payload=None):
        if method == "GET" and "/pulls/" in path and "/comments" not in path:
            return {**self.payload, "body": self.body}
        if method == "GET" and "/issues/" in path and "/comments" in path:
            return self.comments
        if method == "PATCH":
            self.writes += 1
            self.body = payload["body"]
            return {**self.payload, "body": self.body}
        if method == "POST":
            self.writes += 1
            comment = {"id": len(self.comments) + 1, "body": payload["body"]}
            self.comments.append(comment)
            return comment
        raise AssertionError((method, path))


def test_live_revalidation_boundary_blocks_changed_evidence_before_write() -> None:
    normalized = _bound_source()
    calls = 0

    def live_revalidator(context, payload, provider):
        nonlocal calls
        assert context is normalized
        assert payload["head"]["sha"] == normalized.data["candidate"]["head_sha"]
        assert provider is live_provider
        calls += 1
        state = publisher._expected_binding(normalized)
        state["live_revalidation"] = {
            "complete": True,
            "candidate_head_sha": payload["head"]["sha"],
            "snapshot_digest": "snapshot-1",
        }
        if calls == 2:
            state["evidence_digest"] = "e" * 64
        return state

    live_provider = _LiveBoundaryGitHub(normalized, live_revalidator)
    result = publisher.publish(
        normalized,
        live_provider,
        apply=True,
        authorized=True,
        serialized_writer=True,
        initialize_region=True,
    )

    assert result.status == "conflict"
    assert "binding changed" in result.reasons[0]
    assert live_provider.writes == 0
    assert calls == 2


class _ObservedTransportGitHub(publisher.GitHubProvider):
    def __init__(self, normalized):
        super().__init__("token")
        self.normalized = normalized
        self.calls: list[tuple[str, str]] = []
        content = (
            "toolchain:\n  revision: "
            + normalized.data["revision_bindings"][0]["revision"]
            + "\n"
        ).encode()
        blob_sha = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
        self.content_payload = {
            "type": "file",
            "path": ".agent-policy.yml",
            "sha": blob_sha,
            "encoding": "base64",
            "content": base64.b64encode(content).decode(),
        }
        planner_path = publisher.renderer.PLANNER_PATH
        planner_content = (
            ROOT
            / "repository-skills"
            / "land-templates-stack"
            / "scripts"
            / "plan_review_scope.py"
        ).read_bytes()
        planner_blob_sha = hashlib.sha1(
            f"blob {len(planner_content)}\0".encode() + planner_content
        ).hexdigest()
        self.planner_payload = {
            "type": "file",
            "path": planner_path,
            "sha": planner_blob_sha,
            "encoding": "base64",
            "content": base64.b64encode(planner_content).decode(),
        }
        self.metadata = {
            "id": 123,
            "node_id": normalized.data["candidate"]["pull_request"]["id"],
            "number": normalized.data["candidate"]["pull_request"]["number"],
            "body": normalized.data["observed"]["pr_body"]["body"]
            if "pr_body" in normalized.data["observed"]
            else "Human PR text\n",
            "base": {
                "sha": normalized.data["candidate"]["base_sha"],
                "repo": {"id": 9, "full_name": normalized.data["repository"]},
            },
            "head": {"sha": normalized.data["candidate"]["head_sha"]},
        }

    def _request(self, method, path, payload=None):
        del payload
        self.calls.append((method, path))
        if "/contents/.agent-policy.yml" in path:
            return self.content_payload
        if f"/contents/{publisher.renderer.PLANNER_PATH}" in path:
            return self.planner_payload
        if method == "POST" and path == "/graphql":
            return {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            }
        if "/pulls/123" in path and "/comments" not in path:
            return self.metadata
        if "/check-runs" in path:
            return {"check_runs": [], "total_count": 0}
        if "/status" in path:
            return {"statuses": [], "state": "success"}
        if "/pulls/123/reviews" in path:
            return []
        if "/issues/123/comments" in path:
            return []
        if "/pulls/123/comments" in path:
            return []
        if "/issues/123/reactions" in path:
            return []
        raise AssertionError((method, path))


def test_real_live_adapter_composes_observer_planner_gate_and_exact_file_binding() -> None:
    source = source_fixture._source()
    source["observed"]["pr_body"] = {"revision": "body-1", "body": "Human PR text\n"}
    normalized = publisher.renderer.normalize(source)
    provider = _ObservedTransportGitHub(normalized)

    def planner_packet_builder(context, snapshot):
        assert context is normalized
        assert snapshot["complete"] is True
        return copy.deepcopy(normalized.planner_packet)

    def gate_resolver(context, snapshot, packet, result):
        assert context is normalized
        assert snapshot["binding_status"] == "stable"
        binding = {
            "repository": normalized.data["repository"],
            "pull_request_id": normalized.data["candidate"]["pull_request"]["id"],
            "candidate_head_sha": normalized.data["candidate"]["head_sha"],
            "base_sha": normalized.data["candidate"]["base_sha"],
            "effective_base_sha": normalized.data["candidate"]["effective_base_sha"],
            "revision_bindings_digest": publisher.renderer.semantic_digest(
                normalized.data["revision_bindings"]
            ),
            "planner_input_digest": publisher.renderer.semantic_digest(packet),
            "planner_result_digest": publisher.renderer.semantic_digest(result),
        }
        return {
            "status": "passed",
            "input_binding": binding,
            "input_binding_digest": publisher.renderer.semantic_digest(binding),
        }

    def effective_base_resolver(context, payload, snapshot):
        assert context is normalized
        assert snapshot["binding_status"] == "stable"
        return {
            "complete": True,
            "source": "test-effective-base-resolver",
            "sha": normalized.data["candidate"]["effective_base_sha"],
            "candidate_head_sha": payload["head"]["sha"],
            "base_sha": payload["base"]["sha"],
        }

    adapter = publisher.GitHubLiveRevalidationAdapter(
        planner_packet_builder=planner_packet_builder,
        gate_resolver=gate_resolver,
        effective_base_resolver=effective_base_resolver,
    )
    state = adapter(normalized, provider.metadata, provider)

    assert state["live_revalidation"]["complete"] is True
    assert state["revision_bindings_digest"] == publisher.renderer.semantic_digest(
        normalized.data["revision_bindings"]
    )
    assert any("check-runs" in path for _, path in provider.calls)
    assert any("contents/.agent-policy.yml" in path for _, path in provider.calls)


def test_publish_uses_live_adapter_and_refuses_changed_evidence_before_write() -> None:
    source = source_fixture._source()
    source["observed"]["pr_body"] = {"revision": "body-1", "body": "Human PR text\n"}
    seed = publisher.renderer.normalize(source)
    seed_provider = _ObservedTransportGitHub(seed)

    def planner_packet_builder(context, snapshot):
        del snapshot
        return copy.deepcopy(context.planner_packet)

    def gate_resolver(context, snapshot, packet, result):
        del snapshot
        binding = {
            "repository": context.data["repository"],
            "pull_request_id": context.data["candidate"]["pull_request"]["id"],
            "candidate_head_sha": context.data["candidate"]["head_sha"],
            "base_sha": context.data["candidate"]["base_sha"],
            "effective_base_sha": context.data["candidate"]["effective_base_sha"],
            "revision_bindings_digest": publisher.renderer.semantic_digest(
                context.data["revision_bindings"]
            ),
            "planner_input_digest": publisher.renderer.semantic_digest(packet),
            "planner_result_digest": publisher.renderer.semantic_digest(result),
        }
        return {
            "status": "passed",
            "input_binding": binding,
            "input_binding_digest": publisher.renderer.semantic_digest(binding),
        }

    def effective_base_resolver(context, payload, snapshot):
        del snapshot
        return {
            "complete": True,
            "source": "test-live-effective-base",
            "sha": context.data["candidate"]["effective_base_sha"],
            "candidate_head_sha": payload["head"]["sha"],
            "base_sha": payload["base"]["sha"],
        }

    adapter = publisher.GitHubLiveRevalidationAdapter(
        planner_packet_builder=planner_packet_builder,
        gate_resolver=gate_resolver,
        effective_base_resolver=effective_base_resolver,
    )
    observer = publisher._load_observer_entrypoint()
    binding = adapter._observation_candidate(seed, seed_provider.metadata, observer)
    readonly = observer.GhReadonlyProvider(
        api=adapter._observation_api(seed_provider, observer)
    )
    capture = observer.capture_once(
        readonly,
        binding,
        observer.DEFAULT_SURFACES,
        clock=adapter.clock,
        budget=observer.ObservationBudget(
            adapter.clock() + adapter.observation_seconds, clock=adapter.clock
        ),
    )
    assert capture.failure is None
    source["observed"]["snapshot"] = capture.snapshot
    normalized = publisher.renderer.normalize(source)

    class MutableLiveProvider(_ObservedTransportGitHub):
        def __init__(self, normalized_input):
            super().__init__(normalized_input)
            self.live_calls = 0
            self.writes = 0
            self.comments: list[dict[str, object]] = []
            self.live_revalidator = self._live_revalidator

        def _live_revalidator(self, context, payload, provider):
            self.live_calls += 1
            state = dict(adapter(context, payload, provider))
            if self.live_calls == 2:
                state["evidence_digest"] = "e" * 64
            return state

        def _request(self, method, path, payload=None):
            if method == "GET" and "/issues/123/comments" in path:
                self.calls.append((method, path))
                return self.comments
            if method == "PATCH":
                self.writes += 1
                self.calls.append((method, path))
                return {**self.metadata, "body": payload["body"]}
            if method == "POST" and path == "/repos/TakashiSasaki/templates/issues/123/comments":
                self.writes += 1
                self.calls.append((method, path))
                comment = {"id": len(self.comments) + 1, "body": payload["body"]}
                self.comments.append(comment)
                return comment
            return super()._request(method, path, payload)

    provider = MutableLiveProvider(normalized)
    result = publisher.publish(
        normalized,
        provider,
        apply=True,
        authorized=True,
        serialized_writer=True,
        initialize_region=True,
    )

    assert result.status == "conflict"
    assert "binding changed" in result.reasons[0]
    assert provider.live_calls == 2
    assert provider.writes == 0


def test_live_effective_base_is_independent_and_must_be_complete() -> None:
    source = source_fixture._source()
    source["observed"]["pr_body"] = {"revision": "body-1", "body": "Human PR text\n"}
    normalized = publisher.renderer.normalize(source)
    provider = _ObservedTransportGitHub(normalized)
    effective_base = "c" * 40

    def planner_packet_builder(context, snapshot):
        del snapshot
        packet = copy.deepcopy(normalized.planner_packet)
        packet["candidate"]["effective_base_sha"] = effective_base
        return packet

    def gate_resolver(context, snapshot, packet, result):
        del snapshot
        binding = {
            "repository": normalized.data["repository"],
            "pull_request_id": normalized.data["candidate"]["pull_request"]["id"],
            "candidate_head_sha": normalized.data["candidate"]["head_sha"],
            "base_sha": normalized.data["candidate"]["base_sha"],
            "effective_base_sha": effective_base,
            "revision_bindings_digest": publisher.renderer.semantic_digest(
                normalized.data["revision_bindings"]
            ),
            "planner_input_digest": publisher.renderer.semantic_digest(packet),
            "planner_result_digest": publisher.renderer.semantic_digest(result),
        }
        return {
            "status": "passed",
            "input_binding": binding,
            "input_binding_digest": publisher.renderer.semantic_digest(binding),
        }

    def effective_base_resolver(context, payload, snapshot):
        del context, snapshot
        return {
            "complete": True,
            "source": "test-stacked-effective-base",
            "sha": effective_base,
            "candidate_head_sha": payload["head"]["sha"],
            "base_sha": payload["base"]["sha"],
        }

    adapter = publisher.GitHubLiveRevalidationAdapter(
        planner_packet_builder=planner_packet_builder,
        gate_resolver=gate_resolver,
        effective_base_resolver=effective_base_resolver,
    )
    state = adapter(normalized, provider.metadata, provider)
    assert state["effective_base_sha"] == effective_base
    assert state["live_revalidation"]["base_sha"] != state["effective_base_sha"]

    incomplete = publisher.GitHubLiveRevalidationAdapter(
        planner_packet_builder=planner_packet_builder,
        gate_resolver=gate_resolver,
        effective_base_resolver=lambda context, payload, snapshot: {
            "complete": False,
            "source": "incomplete-test-resolver",
            "candidate_head_sha": payload["head"]["sha"],
            "base_sha": payload["base"]["sha"],
        },
    )
    with pytest.raises(publisher.PublicationError, match="effective base is incomplete"):
        incomplete(normalized, provider.metadata, provider)


def test_github_apply_without_live_adapter_cannot_use_static_binding_state() -> None:
    provider = publisher.GitHubProvider("token")

    def metadata(*args, **kwargs):
        return {
            "id": 123,
            "node_id": "PR_node_123",
            "number": 123,
            "body": "",
            "base": {
                "sha": "a" * 40,
                "repo": {"id": 9, "full_name": "TakashiSasaki/templates"},
            },
            "head": {"sha": "b" * 40},
        }

    provider._request = metadata
    with pytest.raises(publisher.PublicationError, match="static replay state"):
        provider.get_current_state("TakashiSasaki/templates", 123, context=object())
