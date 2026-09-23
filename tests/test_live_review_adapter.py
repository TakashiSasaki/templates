from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "repository-skills" / "land-templates-stack" / "scripts"
SOURCE_FIXTURE_PATH = ROOT / "tests" / "test_review_artifacts.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


live_adapter = _load_module("live_review_adapter", SCRIPTS_DIR / "live_review_adapter.py")
source_fixture = _load_module("source_fixture", SOURCE_FIXTURE_PATH)
publisher = live_adapter.publisher


class _MockObservedTransportGitHub(publisher.GitHubProvider):
    def __init__(self, normalized: Any) -> None:
        super().__init__("fake-token", publisher_login="publisher")
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
        # Use simple dummy code for planner payload in tests
        planner_code = (
            b"def plan(packet):\n"
            b"    return {'action': 'reuse_existing_result', 'reasons': ['test']}\n"
        )
        actual_blob = hashlib.sha1(
            f"blob {len(planner_code)}\0".encode() + planner_code
        ).hexdigest()
        # Update normalized planner blob to match
        normalized.data["planner"]["source"]["blob_sha"] = actual_blob
        self.planner_payload = {
            "type": "file",
            "path": planner_path,
            "sha": actual_blob,
            "encoding": "base64",
            "content": base64.b64encode(planner_code).decode(),
        }
        self.commit_tree_sha = "d" * 40
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

    def _request(self, method: str, path: str, payload: Any = None) -> Any:
        del payload
        self.calls.append((method, path))
        if method == "GET" and "/git/commits/" in path:
            revision = path.rsplit("/", 1)[-1]
            return {"sha": revision, "tree": {"sha": self.commit_tree_sha}}
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


@pytest.fixture
def test_normalized_context():
    source = source_fixture._source()
    source["observed"]["pr_body"] = {"revision": "body-1", "body": "Human PR text\n"}
    normalized = publisher.renderer.normalize(
        source,
        trusted_base_sha=source_fixture.TEST_TRUSTED_BASE_SHA,
        candidate_file_resolver=source_fixture._fixture_candidate_file,
    )
    return normalized


def test_live_review_adapter_resolve_happy_path(test_normalized_context) -> None:
    normalized = test_normalized_context
    provider = _MockObservedTransportGitHub(normalized)

    state = live_adapter.resolve(normalized, provider.metadata, provider)

    assert state["live_revalidation"]["complete"] is True
    assert state["live_revalidation"]["candidate_head_sha"] == provider.metadata["head"]["sha"]
    assert state["live_revalidation"]["base_sha"] == provider.metadata["base"]["sha"]
    assert state["effective_base_sha"] == normalized.data["candidate"]["effective_base_sha"]
    assert state["revision_bindings_digest"] == publisher.renderer.semantic_digest(
        normalized.data["revision_bindings"]
    )


def test_live_review_adapter_refuses_head_mismatch(test_normalized_context) -> None:
    normalized = test_normalized_context
    provider = _MockObservedTransportGitHub(normalized)

    tampered_metadata = copy.deepcopy(provider.metadata)
    tampered_metadata["head"]["sha"] = "9" * 40

    with pytest.raises(
        publisher.PublicationError,
        match="target member head is not bound to the live PR head",
    ):
        live_adapter.resolve(normalized, tampered_metadata, provider)


def test_live_review_adapter_refuses_base_mismatch(test_normalized_context) -> None:
    normalized = test_normalized_context
    provider = _MockObservedTransportGitHub(normalized)

    tampered_metadata = copy.deepcopy(provider.metadata)
    tampered_metadata["base"]["sha"] = "8" * 40

    with pytest.raises(
        publisher.PublicationError,
        match="target member base is not bound to the live PR base",
    ):
        live_adapter.resolve(normalized, tampered_metadata, provider)


def test_live_review_adapter_refuses_consumer_pin_mismatch(test_normalized_context) -> None:
    normalized = test_normalized_context
    provider = _MockObservedTransportGitHub(normalized)

    # Change returned toolchain revision in .agent-policy.yml
    bad_content = b"toolchain:\n  revision: 0000000000000000000000000000000000000000\n"
    provider.content_payload = {
        "type": "file",
        "path": ".agent-policy.yml",
        "sha": hashlib.sha1(f"blob {len(bad_content)}\0".encode() + bad_content).hexdigest(),
        "encoding": "base64",
        "content": base64.b64encode(bad_content).decode(),
    }

    with pytest.raises(
        publisher.PublicationError,
        match="consumer configuration blob binding changed|consumer_actual_toolchain claim differs",
    ):
        live_adapter.resolve(normalized, provider.metadata, provider)


def test_live_review_adapter_refuses_altered_tree_binding(test_normalized_context) -> None:
    normalized = test_normalized_context
    normalized.data["candidate"]["integration_base_tree_sha"] = "a" * 40
    provider = _MockObservedTransportGitHub(normalized)
    provider.commit_tree_sha = "b" * 40

    with pytest.raises(
        publisher.PublicationError, match="integration-base tree binding differs"
    ):
        live_adapter.resolve(normalized, provider.metadata, provider)
