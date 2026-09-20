#!/usr/bin/env python3
"""Preview or safely publish artifacts rendered from one bound input.

The default operation is a local preview.  Applying a publication requires
both an explicit ``apply`` flag and explicit authorization for the requested
remote side effects.  A provider implementation must expose current PR
identity, dependency-binding, planner/gate-binding, and body state; missing
revalidation data is an explicit stop condition.

The GitHub adapter uses the existing issue-comment surface for review-request
and provider-side Work-ledger checkpoints.  GitHub's ordinary PR-body update
endpoint does not provide a general conditional compare-and-swap guard, so a
body write additionally requires a caller-authorized serialized writer and a
read/compare/re-read boundary.  A changed body is reported as a conflict and
is never overwritten.
"""

from __future__ import annotations

import argparse
import copy
import http.client
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


def _load_renderer() -> Any:
    path = Path(__file__).with_name("render_review_artifacts.py")
    spec = importlib.util.spec_from_file_location("templates_render_review_artifacts", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the bound review-artifact renderer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = _load_renderer()

ACTION_RECONCILE = "reconcile_existing_request"
ACTION_REUSE = "reuse_existing_result"
ACTION_MISSING = "acquire_missing_input_or_handoff"
REQUEST_ACTIONS = {
    "run_fixed_snapshot_diagnostic",
    "request_independent_delta_review",
    "request_related_stack_review",
}


class PublicationError(RuntimeError):
    """Raised for an adapter or remote-operation error."""


class RemoteAmbiguousError(PublicationError):
    """The remote may have applied a write but its response was lost."""


class PublicationResult:
    """A serializable, non-authoritative publication outcome."""

    __slots__ = ("status", "operations", "reasons", "rendered")

    def __init__(
        self,
        status: str,
        operations: list[dict[str, Any]],
        reasons: list[str],
        rendered: Any,
    ) -> None:
        self.status = status
        self.operations = operations
        self.reasons = reasons
        self.rendered = rendered

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "operations": copy.deepcopy(self.operations),
            "reasons": list(self.reasons),
            "semantic_digest": self.rendered.normalized.semantic_digest,
            "binding_digest": self.rendered.normalized.binding_digest,
            "manifest": copy.deepcopy(self.rendered.manifest),
        }


class RemoteProvider:
    """Small provider surface used by the publisher and fake-based tests."""

    def get_current_state(self, repository: str, number: int) -> dict[str, Any]:
        raise NotImplementedError

    def list_comments(self, repository: str, number: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def update_pr_body(self, repository: str, number: int, body: str) -> Mapping[str, Any]:
        raise NotImplementedError

    def create_comment(self, repository: str, number: int, body: str) -> Mapping[str, Any]:
        raise NotImplementedError


def _json_data(value: Any, name: str) -> Any:
    try:
        return renderer._json_data(value, name)
    except Exception as exc:
        raise PublicationError(str(exc)) from exc


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationError(f"{name} must be a non-empty string")
    return value


def _repository_path(repository: str) -> str:
    repository = _require_string(repository, "repository")
    if repository.count("/") != 1 or any(part in {"", ".", ".."} for part in repository.split("/")):
        raise PublicationError("repository must be an owner/name path")
    return "/repos/" + "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))


class GitHubProvider(RemoteProvider):
    """Bounded GitHub REST adapter with an optional live binding resolver."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        timeout: float = 30.0,
        binding_resolver: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        self.token = _require_string(token, "token")
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.binding_resolver = binding_resolver

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "templates-bound-review-artifacts",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.api_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PublicationError(f"GitHub {method} {path} returned {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as exc:
            if method in {"POST", "PATCH", "PUT", "DELETE"}:
                raise RemoteAmbiguousError(
                    f"GitHub {method} response was ambiguous for {path}: {exc}"
                ) from exc
            raise PublicationError(f"GitHub {method} {path} could not be read: {exc}") from exc
        if not content:
            return {}
        try:
            return json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicationError(f"GitHub {method} {path} returned invalid JSON") from exc

    def get_current_state(self, repository: str, number: int) -> dict[str, Any]:
        path = f"{_repository_path(repository)}/pulls/{number}"
        payload = self._request("GET", path)
        if not isinstance(payload, Mapping):
            raise PublicationError("GitHub PR response must be an object")
        base = payload.get("base")
        head = payload.get("head")
        if not isinstance(base, Mapping) or not isinstance(head, Mapping):
            raise PublicationError("GitHub PR response lacks base/head identities")
        body = payload.get("body") or ""
        state: dict[str, Any] = {
            "repository": repository,
            "pull_request_id": payload.get("node_id") or str(payload.get("id", "")),
            "pull_request_number": payload.get("number"),
            "head_sha": head.get("sha"),
            "candidate_head_sha": head.get("sha"),
            "base_sha": base.get("sha"),
            "effective_base_sha": base.get("sha"),
            "body": body,
            "body_revision": renderer.semantic_digest(body),
            "body_digest": renderer.semantic_digest(body),
        }
        if self.binding_resolver is not None:
            resolved = self.binding_resolver(payload)
            if not isinstance(resolved, Mapping):
                raise PublicationError("binding_resolver must return an object")
            state.update(_json_data(dict(resolved), "binding_resolver result"))
        return state

    def list_comments(self, repository: str, number: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        for page in range(1, 101):
            path = (
                f"{_repository_path(repository)}/issues/{number}/comments?per_page=100&page={page}"
            )
            payload = self._request("GET", path)
            if not isinstance(payload, list):
                raise PublicationError("GitHub comments response must be a list")
            comments.extend(_json_data(payload, "GitHub comments"))
            if len(payload) < 100:
                return comments
        raise PublicationError("GitHub comment pagination exceeded the bounded limit")

    def update_pr_body(self, repository: str, number: int, body: str) -> Mapping[str, Any]:
        result = self._request(
            "PATCH",
            f"{_repository_path(repository)}/pulls/{number}",
            {"body": body},
        )
        if not isinstance(result, Mapping):
            raise PublicationError("GitHub PR update response must be an object")
        return result

    def create_comment(self, repository: str, number: int, body: str) -> Mapping[str, Any]:
        result = self._request(
            "POST",
            f"{_repository_path(repository)}/issues/{number}/comments",
            {"body": body},
        )
        if not isinstance(result, Mapping):
            raise PublicationError("GitHub comment response must be an object")
        return result


def _flatten_state(state: Mapping[str, Any]) -> dict[str, Any]:
    result = _json_data(dict(state), "current provider state")
    nested = result.get("binding")
    if isinstance(nested, Mapping):
        for key, value in nested.items():
            result.setdefault(key, value)
    return result


def _expected_binding(normalized: Any) -> dict[str, Any]:
    data = normalized.data
    candidate = data["candidate"]
    planner = data["planner"]
    return {
        "repository": data["repository"],
        "pull_request_id": candidate["pull_request"]["id"],
        "pull_request_number": candidate["pull_request"]["number"],
        "candidate_head_sha": candidate["head_sha"],
        "head_sha": candidate["head_sha"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "revision_bindings_digest": renderer.semantic_digest(data["revision_bindings"]),
        "planner_input_digest": renderer.semantic_digest(planner["packet"]),
        "planner_result_digest": renderer.semantic_digest(planner["result"]),
        "gate_input_binding_digest": data["gate"]["input_binding_digest"],
        "gate_status": data["gate"]["status"],
        "evidence_digest": renderer.semantic_digest(data["observed"]["facts"]),
    }


def _body_state(state: Mapping[str, Any]) -> tuple[str, str | None, str | None]:
    body = state.get("body")
    body_revision = state.get("body_revision")
    body_digest = state.get("body_digest")
    nested = state.get("pr_body")
    if isinstance(nested, Mapping):
        body = nested.get("body", body)
        body_revision = nested.get("revision", body_revision)
        body_digest = nested.get("body_digest", body_digest)
    if not isinstance(body, str):
        raise PublicationError("current provider state lacks PR body")
    actual_digest = renderer.semantic_digest(body)
    if body_digest is not None and body_digest != actual_digest:
        raise PublicationError("current provider body digest does not match body")
    if body_revision is not None and not isinstance(body_revision, str):
        raise PublicationError("current provider body revision must be a string")
    return body, body_revision, actual_digest


def validate_current_state(
    normalized: Any,
    state: Mapping[str, Any],
    *,
    expected_body: str | None = None,
) -> list[str]:
    """Return fail-closed binding mismatches without inferring missing facts."""

    current = _flatten_state(state)
    expected = _expected_binding(normalized)
    reasons: list[str] = []
    for key, value in expected.items():
        if key not in current:
            reasons.append(f"current_{key}_not_observed")
        elif current[key] != value:
            reasons.append(f"current_{key}_changed")
    body, body_revision, body_digest = _body_state(current)
    expected_observed_body = normalized.data["observed"].get("pr_body")
    if expected_body is None:
        if not isinstance(expected_observed_body, Mapping):
            reasons.append("expected_pr_body_not_observed")
        else:
            expected_body = expected_observed_body["body"]
    if expected_body is not None and body != expected_body:
        reasons.append("pr_body_changed")
    if (
        expected_body is None
        and isinstance(expected_observed_body, Mapping)
        and body_revision is not None
    ):
        expected_revision = expected_observed_body.get("revision")
        if expected_revision is not None and body_revision != expected_revision:
            reasons.append("pr_body_revision_changed")
    if renderer.semantic_digest(body) != body_digest:
        reasons.append("pr_body_digest_unknown")
    return list(dict.fromkeys(reasons))


def _desired_body(normalized: Any, rendered: Any, *, initialize: bool) -> str | None:
    observed_body = normalized.data["observed"].get("pr_body")
    if not isinstance(observed_body, Mapping):
        return None
    try:
        return renderer.replace_generated_region(
            observed_body["body"],
            rendered.files["pr-generated-region.md"],
            initialize=initialize,
        )
    except renderer.RegionOwnershipError:
        return None


def _malformed_region_reason(state: Mapping[str, Any], *, initialize: bool) -> str | None:
    body, _, _ = _body_state(_flatten_state(state))
    start_count = body.count(renderer.GENERATED_REGION_START)
    end_count = body.count(renderer.GENERATED_REGION_END)
    if start_count > 1 or end_count > 1:
        return "generated PR-description markers are duplicated"
    if (start_count == 0) != (end_count == 0):
        return "generated PR-description markers are incomplete"
    if start_count == 1 and body.index(renderer.GENERATED_REGION_END) < body.index(
        renderer.GENERATED_REGION_START
    ):
        return "generated PR-description markers are reversed"
    if start_count == 0 and not initialize:
        return None
    return None


def _validate_for_publication(
    normalized: Any,
    state: Mapping[str, Any],
    *,
    desired_body: str | None,
) -> list[str]:
    reasons = validate_current_state(normalized, state)
    if not reasons or desired_body is None:
        return reasons
    try:
        current_body, _, _ = _body_state(_flatten_state(state))
    except PublicationError:
        return reasons
    if current_body != desired_body:
        return reasons
    return validate_current_state(normalized, state, expected_body=desired_body)


def _state_token(state: Mapping[str, Any]) -> tuple[Any, ...]:
    current = _flatten_state(state)
    body, body_revision, body_digest = _body_state(current)
    return (
        current.get("repository"),
        current.get("pull_request_id"),
        current.get("pull_request_number"),
        current.get("head_sha"),
        current.get("base_sha"),
        current.get("effective_base_sha"),
        current.get("revision_bindings_digest"),
        current.get("planner_input_digest"),
        current.get("planner_result_digest"),
        current.get("gate_input_binding_digest"),
        body_revision,
        body_digest,
        body,
    )


def _marker(comment: Mapping[str, Any], prefix: str, key: str) -> bool:
    body = comment.get("body")
    return isinstance(body, str) and f"<!-- {prefix}:key={key} -->" in body


def _matching_comments(
    comments: Sequence[Mapping[str, Any]], prefix: str, key: str
) -> list[Mapping[str, Any]]:
    return [comment for comment in comments if _marker(comment, prefix, key)]


def _planned_operations(
    normalized: Any,
    current: Mapping[str, Any],
    comments: Sequence[Mapping[str, Any]],
    *,
    initialize: bool,
) -> tuple[list[dict[str, Any]], str]:
    rendered = renderer.render(normalized)
    body, _, _ = _body_state(current)
    try:
        updated_body = renderer.replace_generated_region(
            body,
            rendered.files["pr-generated-region.md"],
            initialize=initialize,
        )
    except renderer.RegionOwnershipError as exc:
        raise PublicationError(str(exc)) from exc
    operations: list[dict[str, Any]] = []
    if updated_body != body:
        operations.append({"type": "update_pr_body", "changed": True})
    request_key = renderer.idempotency_key(normalized, "review-request")
    checkpoint_key = renderer.idempotency_key(normalized, "work-ledger-checkpoint")
    action = normalized.planner_result.get("action")
    request_matches = _matching_comments(comments, renderer.REVIEW_REQUEST_MARKER, request_key)
    checkpoint_matches = _matching_comments(
        comments, renderer.WORK_CHECKPOINT_MARKER, checkpoint_key
    )
    if len(request_matches) > 1 or len(checkpoint_matches) > 1:
        raise PublicationError("duplicate equivalent publication markers require reconciliation")
    if action in REQUEST_ACTIONS and not _has_planner_blocker(normalized):
        if len(request_matches) == 1:
            operations.append(
                {"type": "review_request", "status": "already_present", "key": request_key}
            )
        else:
            operations.append({"type": "review_request", "status": "create", "key": request_key})
    elif action in REQUEST_ACTIONS:
        operations.append(
            {"type": "review_request", "status": "observation_handoff", "key": request_key}
        )
    elif action in {ACTION_RECONCILE, ACTION_REUSE, ACTION_MISSING}:
        operations.append(
            {
                "type": "review_request",
                "status": "planner_"
                + (
                    "reconcile"
                    if action == ACTION_RECONCILE
                    else "reuse"
                    if action == ACTION_REUSE
                    else "handoff"
                ),
                "key": request_key,
            }
        )
    if len(checkpoint_matches) == 1:
        operations.append(
            {"type": "work_checkpoint", "status": "already_present", "key": checkpoint_key}
        )
    else:
        operations.append({"type": "work_checkpoint", "status": "create", "key": checkpoint_key})
    return operations, updated_body


def _has_planner_blocker(normalized: Any) -> bool:
    return any(
        reason.startswith("planner_") or reason.startswith("observation_")
        for reason in normalized.blockers
    )


def _reconcile_comment(
    remote: RemoteProvider,
    repository: str,
    number: int,
    prefix: str,
    key: str,
) -> tuple[str, list[Mapping[str, Any]]]:
    comments = remote.list_comments(repository, number)
    matches = _matching_comments(comments, prefix, key)
    if len(matches) == 1:
        return "reconciled", matches
    if len(matches) > 1:
        return "conflict", matches
    return "ambiguous", matches


def publish(
    normalized: Any,
    remote: RemoteProvider | None = None,
    *,
    apply: bool = False,
    authorized: bool = False,
    serialized_writer: bool = False,
    initialize_region: bool = False,
) -> PublicationResult:
    """Preview or publish all eligible projections with revalidation.

    ``apply=False`` performs no remote reads or writes.  ``authorized`` is a
    separate capability from ``apply``; both are required.  A GitHub PR-body
    write additionally needs ``serialized_writer`` because the REST endpoint
    lacks a general conditional body CAS guard.
    """

    rendered = renderer.render(normalized)
    if not apply:
        operations = [{"type": "local_render", "status": "preview"}]
        return PublicationResult("preview", operations, [], rendered)
    if not authorized:
        return PublicationResult(
            "needs_authorization",
            [],
            ["explicit_remote_write_authorization_required"],
            rendered,
        )
    if remote is None:
        return PublicationResult("blocked", [], ["remote_provider_required"], rendered)
    if not serialized_writer:
        return PublicationResult(
            "needs_serialized_writer",
            [],
            ["pr_body_update_requires_authorized_serialized_writer"],
            rendered,
        )
    candidate = normalized.data["candidate"]
    repository = normalized.data["repository"]
    number = candidate["pull_request"]["number"]
    desired_body = _desired_body(
        normalized,
        rendered,
        initialize=initialize_region,
    )
    try:
        current = remote.get_current_state(repository, number)
        malformed = _malformed_region_reason(current, initialize=initialize_region)
        if malformed is not None:
            return PublicationResult("conflict", [], [malformed], rendered)
        mismatches = _validate_for_publication(
            normalized,
            current,
            desired_body=desired_body,
        )
    except (PublicationError, OSError) as exc:
        return PublicationResult("blocked", [], [str(exc)], rendered)
    if mismatches:
        return PublicationResult("stale", [], mismatches, rendered)
    try:
        comments = remote.list_comments(repository, number)
        operations, updated_body = _planned_operations(
            normalized,
            current,
            comments,
            initialize=initialize_region,
        )
    except PublicationError as exc:
        return PublicationResult("conflict", [], [str(exc)], rendered)

    body_changed = any(
        operation["type"] == "update_pr_body" and operation.get("changed")
        for operation in operations
    )
    if body_changed:
        try:
            before_write = remote.get_current_state(repository, number)
            if _state_token(before_write) != _state_token(current):
                return PublicationResult(
                    "conflict", operations, ["PR body or binding changed before write"], rendered
                )
            before_reasons = _validate_for_publication(
                normalized,
                before_write,
                desired_body=desired_body,
            )
            if before_reasons:
                return PublicationResult("stale", operations, before_reasons, rendered)
            remote.update_pr_body(repository, number, updated_body)
            after_write = remote.get_current_state(repository, number)
            after_body, _, _ = _body_state(after_write)
            if after_body != updated_body:
                return PublicationResult(
                    "conflict",
                    operations,
                    ["PR body did not retain the generated region"],
                    rendered,
                )
            current = after_write
        except RemoteAmbiguousError as exc:
            try:
                reconciled = remote.get_current_state(repository, number)
                after_body, _, _ = _body_state(reconciled)
            except PublicationError:
                return PublicationResult("ambiguous", operations, [str(exc)], rendered)
            if after_body == updated_body:
                operations.append({"type": "update_pr_body", "status": "reconciled"})
                current = reconciled
            else:
                return PublicationResult("ambiguous", operations, [str(exc)], rendered)
        except (PublicationError, OSError) as exc:
            return PublicationResult("blocked", operations, [str(exc)], rendered)

    # Every comment create gets a fresh binding read and a fresh duplicate
    # check.  The provider API does not promise atomic create-if-absent, so a
    # lost response is reconciled rather than retried.
    comment_specs = [
        (
            "review_request",
            renderer.REVIEW_REQUEST_MARKER,
            renderer.idempotency_key(normalized, "review-request"),
            rendered.files["review-request.md"],
        ),
        (
            "work_checkpoint",
            renderer.WORK_CHECKPOINT_MARKER,
            renderer.idempotency_key(normalized, "work-ledger-checkpoint"),
            rendered.files["work-ledger-checkpoint.md"],
        ),
    ]
    for operation_type, prefix, key, body in comment_specs:
        operation = next(item for item in operations if item["type"] == operation_type)
        if operation["status"] != "create":
            continue
        try:
            latest_state = remote.get_current_state(repository, number)
            latest_reasons = _validate_for_publication(
                normalized,
                latest_state,
                desired_body=updated_body,
            )
            if latest_reasons:
                return PublicationResult(
                    "stale",
                    operations,
                    latest_reasons,
                    rendered,
                )
            latest_comments = remote.list_comments(repository, number)
            matches = _matching_comments(latest_comments, prefix, key)
            if len(matches) > 1:
                return PublicationResult(
                    "conflict", operations, [f"duplicate {operation_type} markers"], rendered
                )
            if matches:
                operation["status"] = "already_present"
                continue
            try:
                remote.create_comment(repository, number, body)
            except RemoteAmbiguousError as exc:
                status, matches = _reconcile_comment(remote, repository, number, prefix, key)
                if status == "reconciled":
                    operation["status"] = "reconciled"
                    continue
                return PublicationResult("ambiguous", operations, [str(exc)], rendered)
            status, matches = _reconcile_comment(remote, repository, number, prefix, key)
            if status == "conflict":
                return PublicationResult(
                    "conflict", operations, [f"duplicate {operation_type} markers"], rendered
                )
            if status != "reconciled":
                return PublicationResult(
                    "ambiguous",
                    operations,
                    [f"{operation_type} response could not be reconciled"],
                    rendered,
                )
            operation["status"] = "created"
        except (PublicationError, OSError) as exc:
            return PublicationResult("blocked", operations, [str(exc)], rendered)
    return PublicationResult("published", operations, [], rendered)


def _load_json(path: str) -> dict[str, Any]:
    payload = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PublicationError(f"invalid JSON input: {exc}") from exc
    if not isinstance(value, Mapping):
        raise PublicationError("input must be an object")
    return dict(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish_parser = subparsers.add_parser("publish", help="preview or publish bound artifacts")
    publish_parser.add_argument(
        "--input", default="-", help="structured JSON input, or '-' for stdin"
    )
    publish_parser.add_argument(
        "--repository", help="override repository only when it matches input"
    )
    publish_parser.add_argument(
        "--revalidation-state",
        help="JSON binding state refreshed by the existing observer/planner/gate adapter",
    )
    publish_parser.add_argument(
        "--token", default=os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN"))
    )
    publish_parser.add_argument("--api-url", default="https://api.github.com")
    publish_parser.add_argument("--apply", action="store_true", help="permit remote writes")
    publish_parser.add_argument(
        "--authorize", action="store_true", help="explicitly authorize remote writes"
    )
    publish_parser.add_argument(
        "--serialized-writer",
        action="store_true",
        help="assert the caller owns the serialized PR-body writer boundary",
    )
    publish_parser.add_argument(
        "--initialize-region",
        action="store_true",
        help="explicitly allow appending a missing generated region",
    )
    args = parser.parse_args(argv)
    try:
        normalized = renderer.normalize(_load_json(args.input))
        if args.repository is not None and args.repository != normalized.data["repository"]:
            raise PublicationError("--repository does not match the bound input")
        remote = None
        if args.apply:
            if not args.token:
                raise PublicationError("--token or GH_TOKEN/GITHUB_TOKEN is required for apply")
            binding_resolver = None
            if args.revalidation_state:

                def binding_resolver(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
                    return _load_json(args.revalidation_state)

            remote = GitHubProvider(
                args.token,
                api_url=args.api_url,
                binding_resolver=binding_resolver,
            )
        result = publish(
            normalized,
            remote,
            apply=args.apply,
            authorized=args.authorize,
            serialized_writer=args.serialized_writer,
            initialize_region=args.initialize_region,
        )
    except (renderer.ArtifactInputError, PublicationError, OSError) as exc:
        print(f"ERROR REVIEW_ARTIFACT_PUBLICATION: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.status in {"preview", "published", "reconciled", "duplicate"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
