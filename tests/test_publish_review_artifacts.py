from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

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

    def get_current_state(self, repository: str, number: int) -> dict[str, object]:
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
