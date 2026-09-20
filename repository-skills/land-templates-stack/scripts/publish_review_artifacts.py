#!/usr/bin/env python3
"""Preview or safely publish artifacts rendered from one bound input.

The default operation is a local preview.  Applying a publication requires
both an explicit ``apply`` flag and explicit authorization for the requested
remote side effects.  A provider implementation must expose current PR
identity, dependency-binding, planner/gate-binding, and body state; missing
revalidation data is an explicit stop condition.

The GitHub adapter uses the existing issue-comment surface for review-request
and provider-side Work-ledger checkpoints. GitHub's ordinary PR-body update
endpoint does not provide a general conditional compare-and-swap guard, so all
remote writes additionally require a caller-authorized serialized writer and a
read/compare/re-read boundary. The keyed in-process lock covers the complete
body-and-comment publication sequence; callers must hold the corresponding
distributed writer lock when more than one publisher process can run. A changed
body is reported as a conflict and is never overwritten. Normal GitHub apply
also requires an injected live revalidation adapter; a static replay document
is never an authorization source.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import http.client
import importlib.util
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


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

_PUBLICATION_LOCK_GUARD = threading.Lock()
_PUBLICATION_LOCKS: dict[tuple[str, int], threading.Lock] = {}

# These values come directly from the target PR response and must not be
# replaced by an injected revalidation callback. The callback is allowed to
# contribute independently resolved evidence (including effective-base
# resolution), but it cannot rewrite the provider's identity, candidate, or
# PR-body concurrency state.
_PROVIDER_OBSERVED_STATE_KEYS = frozenset(
    {
        "repository",
        "pull_request_id",
        "pull_request_number",
        "head_sha",
        "candidate_head_sha",
        "base_sha",
        "body",
        "body_revision",
        "body_digest",
        "pr_body",
    }
)


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


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader used by the publisher's immutable input boundary."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_consumer_yaml(text: str) -> Any:
    """Parse consumer YAML without importing mutable checkout code."""

    return yaml.load(text, Loader=_UniqueKeyLoader)


class RemoteProvider:
    """Small provider surface used by the publisher and fake-based tests."""

    def get_current_state(
        self,
        repository: str,
        number: int,
        *,
        context: Any | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_comments(self, repository: str, number: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def update_pr_body(self, repository: str, number: int, body: str) -> Mapping[str, Any]:
        raise NotImplementedError

    def create_comment(self, repository: str, number: int, body: str) -> Mapping[str, Any]:
        raise NotImplementedError

    def create_review_request(
        self,
        repository: str,
        number: int,
        body: str,
        *,
        context: Any | None = None,
    ) -> Mapping[str, Any]:
        """Publish a provider-specific review request.

        The base adapter is deliberately provider-neutral.  Providers that
        require an invocation syntax may override this method; tests and
        other providers retain the ordinary comment surface.
        """

        return self.create_comment(repository, number, body)

    def is_equivalent_review_request(
        self,
        comment: Mapping[str, Any],
        key: str,
        *,
        expected_body: str | None = None,
        context: Any | None = None,
    ) -> bool:
        body = comment.get("body")
        return _marker(comment, renderer.REVIEW_REQUEST_MARKER, key) and (
            expected_body is None or body == expected_body
        )

    def review_request_acknowledgement(
        self,
        repository: str,
        number: int,
        comment: Mapping[str, Any],
    ) -> str:
        """Return provider acknowledgement state without treating it as approval."""

        del repository, number, comment
        return "submitted_unacknowledged"


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
    """Bounded GitHub REST adapter with required live revalidation."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        timeout: float = 30.0,
        live_revalidator: Callable[[Any, Mapping[str, Any], GitHubProvider], Mapping[str, Any]]
        | None = None,
        publisher_login: str | None = None,
    ) -> None:
        self.token = _require_string(token, "token")
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.live_revalidator = live_revalidator
        self._publisher_login = publisher_login

    def _authenticated_login(self) -> str:
        if self._publisher_login is None:
            payload = self._request("GET", "/user")
            if not isinstance(payload, Mapping):
                raise PublicationError("GitHub authenticated-user response must be an object")
            self._publisher_login = _require_string(
                payload.get("login"), "GitHub authenticated-user login"
            )
        return self._publisher_login

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
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except (
                urllib.error.URLError,
                TimeoutError,
                http.client.HTTPException,
                http.client.RemoteDisconnected,
                http.client.IncompleteRead,
                ConnectionResetError,
                ConnectionAbortedError,
                BrokenPipeError,
                EOFError,
                OSError,
            ) as read_exc:
                if method in {"POST", "PATCH", "PUT", "DELETE"}:
                    raise RemoteAmbiguousError(
                        f"GitHub {method} error response was ambiguous for {path}: {read_exc}"
                    ) from read_exc
                raise PublicationError(
                    f"GitHub {method} error response could not be read for {path}: {read_exc}"
                ) from read_exc
            raise PublicationError(f"GitHub {method} {path} returned {exc.code}: {detail}") from exc
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.HTTPException,
            http.client.RemoteDisconnected,
            http.client.IncompleteRead,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            EOFError,
            OSError,
        ) as exc:
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
            if method in {"POST", "PATCH", "PUT", "DELETE"}:
                raise RemoteAmbiguousError(
                    f"GitHub {method} response was ambiguous for {path}: invalid JSON"
                ) from exc
            raise PublicationError(f"GitHub {method} {path} returned invalid JSON") from exc

    def get_current_state(
        self,
        repository: str,
        number: int,
        *,
        context: Any | None = None,
    ) -> dict[str, Any]:
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
        if self.live_revalidator is None:
            raise PublicationError(
                "live revalidation adapter is required for GitHub apply; "
                "a static replay state cannot authorize remote writes"
            )
        if context is None:
            raise PublicationError("live revalidation requires the normalized input context")
        resolved = self.live_revalidator(context, payload, self)
        if not isinstance(resolved, Mapping):
            raise PublicationError("live revalidation adapter must return an object")
        live_state = resolved.get("live_revalidation")
        if (
            not isinstance(live_state, Mapping)
            or live_state.get("complete") is not True
            or live_state.get("candidate_head_sha") != head.get("sha")
        ):
            raise PublicationError(
                "live revalidation adapter did not return a complete current snapshot"
            )
        supplemental = _json_data(dict(resolved), "live revalidation result")
        if any(key in supplemental for key in _PROVIDER_OBSERVED_STATE_KEYS):
            overridden = sorted(
                key for key in _PROVIDER_OBSERVED_STATE_KEYS if key in supplemental
            )
            raise PublicationError(
                "live revalidation cannot override provider-observed fields: "
                + ", ".join(overridden)
            )
        nested_binding = supplemental.get("binding")
        if isinstance(nested_binding, Mapping) and any(
            key in nested_binding for key in _PROVIDER_OBSERVED_STATE_KEYS
        ):
            raise PublicationError(
                "live revalidation cannot override provider-observed binding fields"
            )
        state.update(supplemental)
        return state

    def read_file_at_revision(
        self,
        repository: str,
        revision: str,
        path: str,
    ) -> dict[str, Any]:
        """Read and verify one immutable file at an exact commit."""

        if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise PublicationError("file resolution requires a full candidate commit SHA")
        if not path or path.startswith("/") or ".." in Path(path).parts:
            raise PublicationError("file path is not repository-relative")
        endpoint = (
            f"{_repository_path(repository)}/contents/"
            f"{urllib.parse.quote(path, safe='/')}?ref={urllib.parse.quote(revision, safe='')}"
        )
        payload = self._request("GET", endpoint)
        if not isinstance(payload, Mapping):
            raise PublicationError("GitHub content response must be an object")
        if payload.get("type") != "file" or payload.get("path") != path:
            raise PublicationError("GitHub content response is not the requested file")
        blob_sha = payload.get("sha")
        content = payload.get("content")
        encoding = payload.get("encoding")
        if (
            not isinstance(blob_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob_sha) is None
            or not isinstance(content, str)
            or encoding != "base64"
        ):
            raise PublicationError("GitHub content response lacks verified file identity")
        try:
            raw = base64.b64decode("".join(content.split()), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise PublicationError("GitHub file content is not valid base64") from exc
        actual_blob_sha = hashlib.sha1(
            f"blob {len(raw)}\0".encode("ascii") + raw
        ).hexdigest()
        if actual_blob_sha != blob_sha:
            raise PublicationError("GitHub file blob identity does not match content")
        return {"path": path, "sha": blob_sha, "content": raw}

    def read_tree_at_revision(self, repository: str, revision: str) -> str:
        """Resolve the exact Git tree attached to one immutable commit."""

        if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise PublicationError("tree resolution requires a full commit SHA")
        endpoint = f"{_repository_path(repository)}/git/commits/{revision}"
        payload = self._request("GET", endpoint)
        if not isinstance(payload, Mapping) or payload.get("sha") != revision:
            raise PublicationError("GitHub commit response is not bound to the requested revision")
        tree = payload.get("tree")
        if not isinstance(tree, Mapping):
            raise PublicationError("GitHub commit response lacks tree identity")
        return _full_sha(tree.get("sha"), "GitHub effective-base tree")

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

    @staticmethod
    def _stack_topology(context: Any | None) -> str:
        if context is None:
            return ""
        data = getattr(context, "data", None)
        candidate = data.get("candidate") if isinstance(data, Mapping) else None
        members = candidate.get("members") if isinstance(candidate, Mapping) else None
        if not isinstance(members, list):
            return ""
        lines = ["", "## Exact ordered stack topology"]
        for index, member in enumerate(members, start=1):
            if not isinstance(member, Mapping):
                continue
            pull_request = member.get("pull_request")
            if isinstance(pull_request, Mapping) and isinstance(pull_request.get("number"), int):
                label = f"PR #{pull_request['number']}"
            else:
                label = f"member `{member.get('id', 'unknown')}`"
            lines.append(
                f"- {index}. {label}: base `{member.get('base_sha')}` -> "
                f"head `{member.get('head_sha')}`"
            )
        lines.append("- Dependency order: lower members must qualify before their dependents.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _codex_review_body(body: str, context: Any | None = None) -> str:
        if re.search(r"(?m)^@codex review(?:\s|$)", body):
            trigger = body
        else:
            trigger = "@codex review\n\n" + body
        topology = GitHubProvider._stack_topology(context)
        if topology and "## Exact ordered stack topology" not in trigger:
            trigger = trigger.rstrip() + "\n" + topology
        return trigger

    def create_review_request(
        self,
        repository: str,
        number: int,
        body: str,
        *,
        context: Any | None = None,
    ) -> Mapping[str, Any]:
        return self.create_comment(
            repository,
            number,
            self._codex_review_body(body, context),
        )

    def is_equivalent_review_request(
        self,
        comment: Mapping[str, Any],
        key: str,
        *,
        expected_body: str | None = None,
        context: Any | None = None,
    ) -> bool:
        body = comment.get("body")
        return (
            super().is_equivalent_review_request(
                comment,
                key,
                expected_body=(
                    self._codex_review_body(expected_body, context)
                    if expected_body is not None
                    else None
                ),
                context=context,
            )
            and isinstance(body, str)
            and re.search(r"(?m)^@codex review(?:\s|$)", body) is not None
            and isinstance(comment.get("user"), Mapping)
            and comment["user"].get("login") == self._authenticated_login()
        )

    def review_request_acknowledgement(
        self,
        repository: str,
        number: int,
        comment: Mapping[str, Any],
    ) -> str:
        comment_id = comment.get("id")
        if not isinstance(comment_id, (int, str)):
            return "submitted_unacknowledged"
        reactions = self._request(
            "GET",
            f"{_repository_path(repository)}/issues/comments/{comment_id}/reactions"
            "?per_page=100&page=1",
        )
        if isinstance(reactions, list) and any(
            isinstance(item, Mapping) and item.get("content") == "eyes"
            for item in reactions
        ):
            return "acknowledged"
        return "submitted_unacknowledged"


def _load_observer_entrypoint() -> Any:
    path = Path(__file__).with_name("observe_pr_state.py")
    spec = importlib.util.spec_from_file_location("templates_observe_pr_state", path)
    if spec is None or spec.loader is None:
        raise PublicationError("cannot load the existing PR observation entry point")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_observation_model() -> Any:
    path = Path(__file__).with_name("pr_state_observation.py")
    spec = importlib.util.spec_from_file_location("templates_pr_state_observation", path)
    if spec is None or spec.loader is None:
        raise PublicationError("cannot load the PR observation model")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _snapshot_evidence_digest(snapshot: Mapping[str, Any]) -> str:
    """Digest provider evidence without observation timestamps or pagination noise."""

    projection = copy.deepcopy(dict(snapshot))
    projection.pop("snapshot_digest", None)
    projection.pop("observation", None)
    projection.pop("resume", None)
    surfaces = projection.get("surfaces")
    if isinstance(surfaces, Mapping):
        for surface in surfaces.values():
            if isinstance(surface, Mapping):
                surface.pop("pages", None)
        metadata = surfaces.get("metadata")
        if isinstance(metadata, Mapping):
            metadata_records = metadata.get("records")
            if isinstance(metadata_records, list):
                for record in metadata_records:
                    if isinstance(record, Mapping):
                        for key in (
                            "body",
                            "body_text",
                            "body_html",
                            "updated_at",
                            "comments",
                            "review_comments",
                            "reactions",
                            "comments_url",
                            "review_comments_url",
                        ):
                            record.pop(key, None)
        comments = surfaces.get("comments")
        if isinstance(comments, Mapping):
            records = comments.get("records")
            if isinstance(records, list):
                comments["records"] = [
                    record
                    for record in records
                    if not (
                        isinstance(record, Mapping)
                        and isinstance(record.get("body"), str)
                        and (
                            renderer.REVIEW_REQUEST_MARKER in record["body"]
                            or renderer.WORK_CHECKPOINT_MARKER in record["body"]
                        )
                    )
                ]
    return renderer.semantic_digest(renderer._strip_observation_metadata(projection))


def _member_provider_key(value: Any, name: str) -> tuple[str, str, str]:
    if not isinstance(value, Mapping):
        raise PublicationError(f"{name} provider identity is incomplete")
    provider = value.get("provider")
    repository_id = value.get("repository_id")
    resource_id = value.get("resource_id")
    if not isinstance(provider, str) or not provider.strip():
        raise PublicationError(f"{name} provider identity is incomplete")
    if type(repository_id) is int and repository_id > 0:
        repository_id = str(repository_id)
    if type(resource_id) is int and resource_id > 0:
        resource_id = str(resource_id)
    if not isinstance(repository_id, str) or not repository_id.strip():
        raise PublicationError(f"{name} provider repository identity is incomplete")
    if not isinstance(resource_id, str) or not resource_id.strip():
        raise PublicationError(f"{name} provider resource identity is incomplete")
    return provider, repository_id, resource_id


def _member_binding_projection(normalized: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": member["id"],
            "authority": member["authority"],
            "base_sha": member["base_sha"],
            "head_sha": member["head_sha"],
            "pull_request": {
                "number": member["pull_request"]["number"],
                "provider_identity": copy.deepcopy(
                    member["pull_request"]["provider_identity"]
                ),
                "provider_path": member["pull_request"]["provider_path"],
            },
        }
        for member in normalized.data["candidate"]["members"]
    ]


def _member_binding_digest(normalized: Any) -> str:
    return renderer.semantic_digest(_member_binding_projection(normalized))


def _validate_member_adjacency(
    members: Sequence[Mapping[str, Any]], name: str
) -> None:
    for index in range(1, len(members)):
        previous = members[index - 1]
        current = members[index]
        if current.get("base_sha") != previous.get("head_sha"):
            raise PublicationError(
                f"{name} members are not an ordered base-to-head chain at index {index}"
            )


def _live_member_binding_digest(
    normalized: Any,
    snapshot: Mapping[str, Any],
    live_head_sha: str,
) -> str:
    members = copy.deepcopy(_member_binding_projection(normalized))
    dependencies = snapshot.get("observed_end", {}).get("dependencies", [])
    live_bindings = {
        item.get("id"): item
        for item in dependencies
        if isinstance(item, Mapping)
    }
    candidate = normalized.data["candidate"]
    expected_dependency_ids = {
        member["id"]
        for member in members
        if member["pull_request"]["number"] != candidate["pull_request"]["number"]
    }
    if set(live_bindings) != expected_dependency_ids:
        raise PublicationError("live dependency observation is incomplete")
    for member in members:
        if member["pull_request"]["number"] == candidate["pull_request"]["number"]:
            member["head_sha"] = live_head_sha
        else:
            observed = live_bindings.get(member["id"])
            if not isinstance(observed, Mapping):
                raise PublicationError(
                    f"live dependency observation lacks member {member['id']}"
                )
            member["head_sha"] = _full_sha(
                observed.get("head_sha"),
                f"live dependency {member['id']} head",
            )
            member["base_sha"] = _full_sha(
                observed.get("base_sha"),
                f"live dependency {member['id']} base",
            )
    _validate_member_adjacency(members, "live observed stack")
    return renderer.semantic_digest(members)


def _full_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise PublicationError(f"{name} must be a lowercase full SHA")
    return value


def _resolve_effective_base(
    resolver: Callable[[Any, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    normalized: Any,
    payload: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    live_head: str,
    live_base: str,
) -> tuple[str, dict[str, Any]]:
    try:
        result = resolver(normalized, payload, snapshot)
    except PublicationError:
        raise
    except Exception as exc:
        raise PublicationError(f"live effective-base resolver failed: {exc}") from exc
    if not isinstance(result, Mapping):
        raise PublicationError("live effective-base resolver must return an object")
    if result.get("complete") is not True:
        raise PublicationError("live effective base is incomplete")
    source = result.get("source")
    if not isinstance(source, str) or not source.strip():
        raise PublicationError("live effective base lacks a resolver identity")
    if result.get("candidate_head_sha") != live_head:
        raise PublicationError("live effective base is bound to a different candidate head")
    if result.get("base_sha") != live_base:
        raise PublicationError("live effective base is bound to a different PR base")
    effective_base = _full_sha(result.get("sha"), "live effective base")
    return effective_base, _json_data(dict(result), "live effective-base result")


class GitHubLiveRevalidationAdapter:
    """Compose the existing observer, planner, gate, and exact-file resolver.

    The planner packet builder and gate resolver are injected because their
    semantic owners already live outside this publisher.  This adapter only
    coordinates them and verifies their candidate bindings; it never decides
    review scope or acceptance itself.
    """

    def __init__(
        self,
        *,
        planner_packet_builder: Callable[[Any, Mapping[str, Any]], Mapping[str, Any]],
        gate_resolver: Callable[
            [Any, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]
        ],
        effective_base_resolver: Callable[
            [Any, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]
        ],
        clock: Callable[[], float] = time.time,
        observation_seconds: float = 60.0,
    ) -> None:
        self.planner_packet_builder = planner_packet_builder
        self.gate_resolver = gate_resolver
        self.effective_base_resolver = effective_base_resolver
        self.clock = clock
        self.observation_seconds = observation_seconds

    @staticmethod
    def _observation_candidate(
        normalized: Any,
        payload: Mapping[str, Any],
        observer: Any,
    ) -> Any:
        candidate = normalized.data["candidate"]
        base = payload.get("base")
        head = payload.get("head")
        repository = base.get("repo") if isinstance(base, Mapping) else None
        repository_id = repository.get("id") if isinstance(repository, Mapping) else None
        live_repository = (
            repository.get("full_name") if isinstance(repository, Mapping) else None
        )
        if live_repository != normalized.data["repository"]:
            raise PublicationError("live PR repository does not match the bound input")
        live_number = payload.get("number")
        if type(live_number) is not int or live_number != candidate["pull_request"]["number"]:
            raise PublicationError("live PR number does not match the bound input")
        live_head = _full_sha(
            head.get("sha") if isinstance(head, Mapping) else None,
            "live PR head",
        )
        live_base = _full_sha(
            base.get("sha") if isinstance(base, Mapping) else None,
            "live PR base",
        )
        resource_id = payload.get("id")
        if type(repository_id) is not int or type(resource_id) is not int:
            raise PublicationError("live PR immutable provider identity is incomplete")

        raw_members = candidate.get("members")
        if not isinstance(raw_members, list) or not raw_members:
            raise PublicationError("candidate topology must contain stack members")
        dependencies: list[dict[str, Any]] = []
        normalized_members: list[dict[str, Any]] = []
        target_members: list[Mapping[str, Any]] = []
        seen_member_ids: set[str] = set()
        seen_pr_numbers: set[int] = set()
        seen_provider_identities: set[tuple[str, str, str]] = set()
        live_provider_key = ("github", str(repository_id), str(resource_id))
        for index, member in enumerate(raw_members):
            if not isinstance(member, Mapping):
                raise PublicationError(f"candidate.members[{index}] must be an object")
            member_id = member.get("id")
            if not isinstance(member_id, str) or not member_id.strip():
                raise PublicationError(f"candidate.members[{index}].id is invalid")
            if member_id in seen_member_ids:
                raise PublicationError("candidate topology contains duplicate member IDs")
            seen_member_ids.add(member_id)
            member_pr = member.get("pull_request")
            if not isinstance(member_pr, Mapping):
                raise PublicationError(
                    f"candidate.members[{index}] lacks an exact pull-request binding"
                )
            member_number = member_pr.get("number")
            if type(member_number) is not int or member_number <= 0:
                raise PublicationError(
                    f"candidate.members[{index}].pull_request.number is invalid"
                )
            provider_identity = member_pr.get("provider_identity")
            if not isinstance(provider_identity, Mapping):
                raise PublicationError(
                    f"candidate.members[{index}] lacks provider identity for observation"
                )
            provider_key = _member_provider_key(
                provider_identity, f"candidate.members[{index}].pull_request"
            )
            if provider_key[0] != "github":
                raise PublicationError("live member observation requires GitHub identities")
            if member_number in seen_pr_numbers:
                raise PublicationError("candidate topology contains duplicate PR numbers")
            if provider_key in seen_provider_identities:
                raise PublicationError("candidate topology contains duplicate provider identities")
            seen_pr_numbers.add(member_number)
            seen_provider_identities.add(provider_key)
            provider_path = member_pr.get(
                "provider_path",
                f"/repos/{normalized.data['repository']}/pulls/{member_number}",
            )
            expected_path = f"/repos/{normalized.data['repository']}/pulls/{member_number}"
            if provider_path != expected_path:
                raise PublicationError(
                    f"candidate.members[{index}] provider path is not bound to its PR"
                )
            member_authority = member.get("authority")
            if not isinstance(member_authority, str) or not member_authority.strip():
                raise PublicationError(f"candidate.members[{index}].authority is invalid")
            member_head = _full_sha(member.get("head_sha"), f"candidate.members[{index}].head_sha")
            member_base = _full_sha(member.get("base_sha"), f"candidate.members[{index}].base_sha")
            normalized_member = {
                "id": member_id,
                "authority": member_authority,
                "head_sha": member_head,
                "base_sha": member_base,
                "pull_request": {
                    "number": member_number,
                    "provider_identity": {
                        "provider": provider_key[0],
                        "repository_id": provider_key[1],
                        "resource_id": provider_key[2],
                    },
                    "provider_path": provider_path,
                },
            }
            normalized_members.append(normalized_member)
            if member_number == live_number:
                target_members.append(normalized_member)
            else:
                dependencies.append(
                    {
                        "id": member_id,
                        "authority": member_authority,
                        "expected_head_sha": member_head,
                        "expected_base_sha": member_base,
                        "provider_identity": normalized_member["pull_request"][
                            "provider_identity"
                        ],
                        "provider_path": provider_path,
                    }
                )
        _validate_member_adjacency(normalized_members, "candidate stack")
        if len(target_members) != 1:
            raise PublicationError(
                "candidate topology must identify the live target PR exactly once"
            )
        target_member = target_members[0]
        if target_member["head_sha"] != live_head:
            raise PublicationError("target member head is not bound to the live PR head")
        if target_member["base_sha"] != live_base:
            raise PublicationError("target member base is not bound to the live PR base")
        if live_provider_key not in seen_provider_identities:
            raise PublicationError("target member provider identity is not live-bound")
        target_identity = candidate["pull_request"].get("provider_identity")
        if _member_provider_key(target_identity, "candidate.pull_request") != live_provider_key:
            raise PublicationError("candidate target provider identity does not match live PR")
        return observer.CandidateBinding.from_mapping(
            {
                "repository": normalized.data["repository"],
                "number": live_number,
                "id": str(resource_id),
                "provider_identity": {
                    "provider": "github",
                    "repository_id": repository_id,
                    "resource_id": resource_id,
                },
                "expected_head_sha": live_head,
                "expected_base_sha": live_base,
                "dependencies": dependencies,
            }
        )

    @staticmethod
    def _observation_api(provider: GitHubProvider, observer: Any) -> Callable[..., Any]:
        def api(
            arguments: Sequence[str],
            *,
            timeout: float = 30.0,
            budget: Any = None,
        ) -> Any:
            del timeout
            values = list(arguments)
            paginate = values and values[0] == "--paginate"
            if paginate:
                values = values[1:]
            if not values:
                raise observer.ProviderFailure("malformed", "observation endpoint is missing")
            try:
                if values[0] == "graphql":
                    query: str | None = None
                    variables: dict[str, Any] = {}
                    index = 1
                    while index < len(values):
                        flag = values[index]
                        if flag not in {"-f", "-F"} or index + 1 >= len(values):
                            raise observer.ProviderFailure(
                                "malformed", "unsupported GraphQL observation argument"
                            )
                        name, separator, raw = values[index + 1].partition("=")
                        if not separator:
                            raise observer.ProviderFailure(
                                "malformed", "malformed GraphQL observation argument"
                            )
                        if name == "query":
                            query = raw
                        else:
                            variables[name] = (
                                int(raw)
                                if flag == "-F" and raw.isdigit()
                                else raw
                            )
                        index += 2
                    if query is None:
                        raise observer.ProviderFailure("malformed", "GraphQL query is missing")
                    payload = provider._request(
                        "POST", "/graphql", {"query": query, "variables": variables}
                    )
                    return observer.ApiResponse(payload)

                endpoint = values[0]
                pages: list[Any] = []
                for page in range(1, 101):
                    if budget is not None:
                        budget.check()
                    separator = "&" if "?" in endpoint else "?"
                    page_endpoint = f"{endpoint}{separator}per_page=100&page={page}"
                    payload = provider._request("GET", page_endpoint)
                    pages.append(payload)
                    if isinstance(payload, list):
                        if len(payload) < 100:
                            break
                    elif isinstance(payload, Mapping):
                        list_values = [
                            value
                            for key, value in payload.items()
                            if key in {"check_runs", "statuses"} and isinstance(value, list)
                        ]
                        if not list_values or any(len(value) < 100 for value in list_values):
                            break
                    else:
                        break
                else:
                    raise observer.ProviderFailure(
                        "incomplete", "observation pagination exceeded the bounded limit"
                    )
                return observer.ApiResponse(pages)
            except observer.ProviderFailure:
                raise
            except Exception as exc:
                raise observer.ProviderFailure("provider", str(exc)) from exc

        return api

    @staticmethod
    def _toolchain_revision(
        provider: GitHubProvider,
        normalized: Any,
        candidate_head: str,
    ) -> None:
        binding = next(
            (
                item
                for item in normalized.data["revision_bindings"]
                if item["role"] == "consumer_actual_toolchain"
            ),
            None,
        )
        if not isinstance(binding, Mapping) or binding.get("status") != "bound":
            raise PublicationError("consumer_actual_toolchain must be bound for live apply")
        source = binding.get("source")
        if not isinstance(source, Mapping):
            raise PublicationError("consumer_actual_toolchain source is incomplete")
        if source.get("candidate_head_sha") != candidate_head:
            raise PublicationError(
                "consumer_actual_toolchain source is not bound to the live candidate head"
            )
        path = source.get("path")
        field = source.get("field")
        if path != ".agent-policy.yml" or field != "toolchain.revision":
            raise PublicationError(
                "live consumer pin verification requires .agent-policy.yml#toolchain.revision"
            )
        resolved = provider.read_file_at_revision(
            normalized.data["repository"], candidate_head, path
        )
        if source.get("blob_sha") is not None and source["blob_sha"] != resolved["sha"]:
            raise PublicationError("consumer configuration blob binding changed")
        try:
            document = _load_consumer_yaml(resolved["content"].decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise PublicationError("consumer configuration is not UTF-8 YAML") from exc
        except PublicationError:
            raise
        except Exception as exc:
            raise PublicationError(f"consumer configuration is malformed: {exc}") from exc
        current: Any = document
        for part in field.split("."):
            if not isinstance(current, Mapping) or part not in current:
                raise PublicationError("consumer toolchain.revision is missing")
            current = current[part]
        actual = _full_sha(current, "consumer toolchain.revision")
        if actual != binding.get("revision"):
            raise PublicationError(
                "consumer_actual_toolchain claim differs from the exact candidate configuration"
            )

    def __call__(
        self,
        normalized: Any,
        payload: Mapping[str, Any],
        provider: GitHubProvider,
    ) -> Mapping[str, Any]:
        observer = _load_observer_entrypoint()
        binding = self._observation_candidate(normalized, payload, observer)
        readonly = observer.GhReadonlyProvider(api=self._observation_api(provider, observer))
        deadline = self.clock() + self.observation_seconds
        capture = observer.capture_once(
            readonly,
            binding,
            observer.DEFAULT_SURFACES,
            clock=self.clock,
            budget=observer.ObservationBudget(deadline, clock=self.clock),
        )
        if capture.failure is not None:
            raise PublicationError(
                f"live PR observation {capture.failure.category}: {capture.failure}"
            )
        snapshot = capture.snapshot
        if not isinstance(snapshot, Mapping):
            raise PublicationError("live PR observation did not produce a snapshot")
        try:
            _load_observation_model().validate_snapshot(snapshot)
        except Exception as exc:
            raise PublicationError(f"live PR observation is invalid: {exc}") from exc
        if snapshot.get("complete") is not True or snapshot.get("binding_status") != "stable":
            raise PublicationError("live PR observation is incomplete or stale")

        live_head = _full_sha(payload.get("head", {}).get("sha"), "live PR head")
        live_base = _full_sha(payload.get("base", {}).get("sha"), "live PR base")
        effective_base_sha, effective_base_binding = _resolve_effective_base(
            self.effective_base_resolver,
            normalized,
            payload,
            snapshot,
            live_head,
            live_base,
        )
        declared_integration_tree = normalized.data["candidate"].get(
            "integration_base_tree_sha"
        )
        if declared_integration_tree is not None:
            declared_integration_tree = _full_sha(
                declared_integration_tree, "candidate.integration_base_tree_sha"
            )
            live_integration_tree = provider.read_tree_at_revision(
                normalized.data["repository"], effective_base_sha
            )
            if live_integration_tree != declared_integration_tree:
                raise PublicationError(
                    "integration-base tree binding differs from the live effective-base tree"
                )
        self._toolchain_revision(provider, normalized, live_head)
        try:
            packet = _json_data(
                dict(self.planner_packet_builder(normalized, snapshot)),
                "live planner packet",
            )
            if not isinstance(packet, Mapping):
                raise PublicationError("live planner packet must be an object")
            packet_candidate = packet.get("candidate")
            if (
                not isinstance(packet_candidate, Mapping)
                or packet_candidate.get("head_sha") != live_head
                or packet_candidate.get("base_sha") != live_base
                or packet_candidate.get("effective_base_sha") != effective_base_sha
            ):
                raise PublicationError(
                    "live planner packet is not bound to the current candidate/base"
                )
            planner_source = normalized.data["planner"]["source"]
            planner_file = provider.read_file_at_revision(
                normalized.data["repository"],
                planner_source["revision"],
                planner_source["path"],
            )
            planner_result = renderer.execute_bound_planner(
                planner_source,
                packet,
                content=planner_file["content"],
                actual_blob=planner_file["sha"],
            )
        except PublicationError:
            raise
        except Exception as exc:
            raise PublicationError(f"live planner could not run: {exc}") from exc
        try:
            gate = _json_data(
                dict(self.gate_resolver(normalized, snapshot, packet, planner_result)),
                "live gate result",
            )
        except PublicationError:
            raise
        except Exception as exc:
            raise PublicationError(f"live gate resolver failed: {exc}") from exc
        if not isinstance(gate, Mapping):
            raise PublicationError("live gate resolver must return an object")
        gate_status = gate.get("status")
        gate_input_digest = gate.get("input_binding_digest")
        if not isinstance(gate_status, str) or not isinstance(gate_input_digest, str):
            raise PublicationError("live gate result lacks status or input binding digest")
        gate_binding = gate.get("input_binding")
        expected_gate_binding = {
            "repository": normalized.data["repository"],
            "pull_request_id": normalized.data["candidate"]["pull_request"]["id"],
            "candidate_head_sha": live_head,
            "base_sha": live_base,
            "effective_base_sha": effective_base_sha,
            "revision_bindings_digest": renderer.semantic_digest(
                normalized.data["revision_bindings"]
            ),
            "planner_input_digest": renderer.semantic_digest(packet),
            "planner_result_digest": renderer.semantic_digest(planner_result),
        }
        if not isinstance(gate_binding, Mapping) or any(
            gate_binding.get(key) != value for key, value in expected_gate_binding.items()
        ):
            raise PublicationError("live gate result is bound to different inputs")
        if renderer.semantic_digest(dict(gate_binding)) != gate_input_digest:
            raise PublicationError("live gate input binding digest is invalid")
        return {
            "revision_bindings_digest": renderer.semantic_digest(
                normalized.data["revision_bindings"]
            ),
            "candidate_members_digest": _live_member_binding_digest(
                normalized, snapshot, live_head
            ),
            "planner_input_digest": renderer.semantic_digest(packet),
            "planner_result_digest": renderer.semantic_digest(planner_result),
            "gate_input_binding_digest": gate_input_digest,
            "gate_status": gate_status,
            "evidence_digest": gate.get("evidence_digest", _snapshot_evidence_digest(snapshot)),
            "live_snapshot_digest": _snapshot_evidence_digest(snapshot),
            "effective_base_sha": effective_base_sha,
            "effective_base_binding": effective_base_binding,
            **(
                {"integration_base_tree_sha": declared_integration_tree}
                if declared_integration_tree is not None
                else {}
            ),
            "live_revalidation": {
                "complete": True,
                "snapshot_digest": snapshot.get("snapshot_digest"),
                "candidate_head_sha": live_head,
                "base_sha": live_base,
                "effective_base_sha": effective_base_sha,
            },
        }


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
    expected = {
        "repository": data["repository"],
        "pull_request_id": candidate["pull_request"]["id"],
        "pull_request_number": candidate["pull_request"]["number"],
        "candidate_head_sha": candidate["head_sha"],
        "head_sha": candidate["head_sha"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "revision_bindings_digest": renderer.semantic_digest(data["revision_bindings"]),
        "candidate_members_digest": _member_binding_digest(normalized),
        "planner_input_digest": renderer.semantic_digest(planner["packet"]),
        "planner_result_digest": renderer.semantic_digest(planner["result"]),
        "gate_input_binding_digest": data["gate"]["input_binding_digest"],
        "gate_status": data["gate"]["status"],
        "evidence_digest": (
            _snapshot_evidence_digest(data["observed"]["snapshot"])
            if isinstance(data["observed"].get("snapshot"), Mapping)
            else renderer.semantic_digest(data["observed"]["facts"])
        ),
    }
    if "integration_base_tree_sha" in candidate:
        expected["integration_base_tree_sha"] = candidate["integration_base_tree_sha"]
    return expected


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
        current.get("candidate_members_digest"),
        current.get("planner_input_digest"),
        current.get("planner_result_digest"),
        current.get("gate_input_binding_digest"),
        current.get("evidence_digest"),
        current.get("live_snapshot_digest"),
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


def _matching_review_requests(
    remote: RemoteProvider,
    comments: Sequence[Mapping[str, Any]],
    key: str,
    expected_body: str,
    context: Any,
) -> list[Mapping[str, Any]]:
    return [
        comment
        for comment in comments
        if remote.is_equivalent_review_request(
            comment, key, expected_body=expected_body, context=context
        )
    ]


def _review_request_matcher(
    remote: RemoteProvider, expected_body: str, context: Any
) -> Callable[[Mapping[str, Any], str], bool]:
    def match(comment: Mapping[str, Any], key: str) -> bool:
        return remote.is_equivalent_review_request(
            comment, key, expected_body=expected_body, context=context
        )

    return match


def _checkpoint_content_matches(
    matches: Sequence[Mapping[str, Any]], rendered_body: str
) -> bool:
    return len(matches) == 1 and matches[0].get("body") == rendered_body


def _planned_operations(
    normalized: Any,
    remote: RemoteProvider,
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
    request_matches = _matching_review_requests(
        remote,
        comments,
        request_key,
        rendered.files["review-request.md"],
        normalized,
    )
    checkpoint_matches = _matching_comments(
        comments, renderer.WORK_CHECKPOINT_MARKER, checkpoint_key
    )
    if len(request_matches) > 1 or len(checkpoint_matches) > 1:
        raise PublicationError("duplicate equivalent publication markers require reconciliation")
    if checkpoint_matches and not _checkpoint_content_matches(
        checkpoint_matches, rendered.files["work-ledger-checkpoint.md"]
    ):
        raise PublicationError("checkpoint marker content does not match current resume state")
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
    matcher: Callable[[Mapping[str, Any], str], bool] | None = None,
) -> tuple[str, list[Mapping[str, Any]]]:
    comments = remote.list_comments(repository, number)
    matches = (
        [comment for comment in comments if matcher(comment, key)]
        if matcher is not None
        else _matching_comments(comments, prefix, key)
    )
    if len(matches) == 1:
        return "reconciled", matches
    if len(matches) > 1:
        return "conflict", matches
    return "ambiguous", matches


def _current_state(
    remote: RemoteProvider,
    repository: str,
    number: int,
    normalized: Any,
) -> dict[str, Any]:
    return remote.get_current_state(repository, number, context=normalized)


def _record_review_acknowledgement(
    remote: RemoteProvider,
    repository: str,
    number: int,
    operation: dict[str, Any],
    comment: Mapping[str, Any],
) -> None:
    try:
        operation["acknowledgement"] = remote.review_request_acknowledgement(
            repository, number, comment
        )
    except PublicationError as exc:
        # The request itself has already been reconciled.  A failed follow-up
        # acknowledgement query must not turn a confirmed write into a retry.
        operation["acknowledgement"] = "unknown"
        operation["acknowledgement_error"] = str(exc)


def _publication_lock(normalized: Any) -> threading.Lock:
    candidate = normalized.data["candidate"]
    key = (normalized.data["repository"], candidate["pull_request"]["number"])
    with _PUBLICATION_LOCK_GUARD:
        return _PUBLICATION_LOCKS.setdefault(key, threading.Lock())


def publish(
    normalized: Any,
    remote: RemoteProvider | None = None,
    *,
    apply: bool = False,
    authorized: bool = False,
    serialized_writer: bool = False,
    initialize_region: bool = False,
) -> PublicationResult:
    """Preview or publish while serializing every remote write for this PR."""

    if not apply or not authorized or not serialized_writer:
        return _publish_authorized(
            normalized,
            remote,
            apply=apply,
            authorized=authorized,
            serialized_writer=serialized_writer,
            initialize_region=initialize_region,
        )
    lock = _publication_lock(normalized)
    if not lock.acquire(blocking=False):
        return PublicationResult(
            "conflict",
            [],
            ["another serialized publication is already in progress for this PR"],
            renderer.render(normalized),
        )
    try:
        return _publish_authorized(
            normalized,
            remote,
            apply=apply,
            authorized=authorized,
            serialized_writer=serialized_writer,
            initialize_region=initialize_region,
        )
    finally:
        lock.release()


def _publish_authorized(
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
    or comment write additionally needs ``serialized_writer`` because the
    provider has no general conditional create/update guard.
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
        current = _current_state(remote, repository, number, normalized)
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
            remote,
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
            before_write = _current_state(remote, repository, number, normalized)
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
            after_write = _current_state(remote, repository, number, normalized)
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
                reconciled = _current_state(remote, repository, number, normalized)
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
            "work_checkpoint",
            renderer.WORK_CHECKPOINT_MARKER,
            renderer.idempotency_key(normalized, "work-ledger-checkpoint"),
            rendered.files["work-ledger-checkpoint.md"],
        ),
        (
            "review_request",
            renderer.REVIEW_REQUEST_MARKER,
            renderer.idempotency_key(normalized, "review-request"),
            rendered.files["review-request.md"],
        ),
    ]
    for operation_type, prefix, key, body in comment_specs:
        operation = next(item for item in operations if item["type"] == operation_type)
        if operation["status"] != "create":
            continue
        try:
            latest_state = _current_state(remote, repository, number, normalized)
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
            matches = (
                _matching_review_requests(
                    remote,
                    latest_comments,
                    key,
                    body,
                    normalized,
                )
                if operation_type == "review_request"
                else _matching_comments(latest_comments, prefix, key)
            )
            # Comment enumeration is itself a remote read and may paginate.
            # Revalidate after that scan, immediately before the mutation, so
            # a head/base/body/evidence change during enumeration cannot be
            # authorized by the earlier snapshot.
            post_scan_state = _current_state(remote, repository, number, normalized)
            if _state_token(post_scan_state) != _state_token(latest_state):
                return PublicationResult(
                    "conflict",
                    operations,
                    [f"binding changed during {operation_type} duplicate scan"],
                    rendered,
                )
            post_scan_reasons = _validate_for_publication(
                normalized,
                post_scan_state,
                desired_body=updated_body,
            )
            if post_scan_reasons:
                return PublicationResult(
                    "stale", operations, post_scan_reasons, rendered
                )
            if len(matches) > 1:
                return PublicationResult(
                    "conflict", operations, [f"duplicate {operation_type} markers"], rendered
                )
            if matches:
                if operation_type == "work_checkpoint" and not _checkpoint_content_matches(
                    matches, body
                ):
                    return PublicationResult(
                        "conflict",
                        operations,
                        ["checkpoint marker content does not match current resume state"],
                        rendered,
                    )
                operation["status"] = "already_present"
                continue
            try:
                if operation_type == "review_request":
                    created_comment = remote.create_review_request(
                        repository, number, body, context=normalized
                    )
                else:
                    created_comment = remote.create_comment(repository, number, body)
            except RemoteAmbiguousError as exc:
                status, matches = _reconcile_comment(
                    remote,
                    repository,
                    number,
                    prefix,
                    key,
                    _review_request_matcher(remote, body, normalized)
                    if operation_type == "review_request"
                    else None,
                )
                if status == "reconciled":
                    operation["status"] = "reconciled"
                    if operation_type == "review_request":
                        _record_review_acknowledgement(
                            remote, repository, number, operation, matches[0]
                        )
                    continue
                return PublicationResult("ambiguous", operations, [str(exc)], rendered)
            status, matches = _reconcile_comment(
                remote,
                repository,
                number,
                prefix,
                key,
                _review_request_matcher(remote, body, normalized)
                if operation_type == "review_request"
                else None,
            )
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
            if operation_type == "review_request":
                _record_review_acknowledgement(
                    remote,
                    repository,
                    number,
                    operation,
                    created_comment if isinstance(created_comment, Mapping) else matches[0],
                )
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


def _load_callable(specification: str) -> Callable[..., Any]:
    """Load an explicitly selected live adapter as ``module:function`` or file:function."""

    module_name, separator, function_name = specification.partition(":")
    if not separator or not module_name or not function_name:
        raise PublicationError("--live-adapter must be MODULE:FUNCTION or FILE.py:FUNCTION")
    module_path = Path(module_name)
    if module_path.is_file():
        module_spec = importlib.util.spec_from_file_location(
            "templates_live_review_adapter", module_path
        )
        if module_spec is None or module_spec.loader is None:
            raise PublicationError(f"cannot load live adapter module: {module_name}")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        module = __import__(module_name, fromlist=[function_name])
    callback = getattr(module, function_name, None)
    if not callable(callback):
        raise PublicationError(f"live adapter is not callable: {specification}")
    return callback


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
        "--live-adapter",
        help=(
            "MODULE:FUNCTION or FILE.py:FUNCTION that composes the live observer, "
            "planner, gate, and exact revision resolvers; required for apply"
        ),
    )
    publish_parser.add_argument(
        "--replay-state",
        help="offline diagnostic JSON only; it can never authorize an apply",
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
        help=(
            "assert the caller owns the serialized writer boundary for the "
            "complete PR-body and comment publication"
        ),
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
            if args.replay_state:
                raise PublicationError(
                    "--replay-state is offline-only and cannot authorize apply"
                )
            if not args.live_adapter:
                raise PublicationError("--live-adapter is required for apply")
            live_revalidator = _load_callable(args.live_adapter)

            remote = GitHubProvider(
                args.token,
                api_url=args.api_url,
                live_revalidator=live_revalidator,
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
