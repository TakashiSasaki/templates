#!/usr/bin/env python3
"""Normalize one bound change input and render its review projections.

The module is deliberately provider-neutral and side-effect free.  It accepts
facts gathered by the existing PR observer, calls the existing immutable review
scope planner, and produces deterministic projections for a review packet, a
review request, a protected PR-description region, and a provider-side Work
ledger checkpoint.  It never decides whether a finding is valid, whether a
candidate is accepted, or whether a merge is authorized.

The input contract is ``repository-change-review-artifacts`` version 1.  The
``revision_bindings`` list is intentionally role based: a consumer's actual
toolchain pin and a prospective canonical candidate are different facts even
when they happen to contain the same SHA.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

INPUT_KIND = "repository-change-review-artifacts"
INPUT_SCHEMA_VERSION = 1
PLANNER_SCHEMA_VERSION = 2
REPOSITORY = "TakashiSasaki/templates"
FULL_SHA = re.compile(r"[0-9a-f]{40}")

PLANNER_PATH = "repository-skills/land-templates-stack/scripts/plan_review_scope.py"
OBSERVER_PATH = "repository-skills/land-templates-stack/scripts/pr_state_observation.py"
TRUSTED_SOURCE_MANIFEST_PATH = ".agents/skills/land-templates-stack/source.json"

GENERATED_REGION_START = "<!-- codex:review-artifacts:v1:start -->"
GENERATED_REGION_END = "<!-- codex:review-artifacts:v1:end -->"
REVIEW_REQUEST_MARKER = "codex-review-request:v1"
WORK_CHECKPOINT_MARKER = "codex-work-ledger:v1"

REVISION_ROLES = (
    "consumer_actual_toolchain",
    "prospective_canonical_candidate",
    "trusted_maintainer_source",
    "publication_provider",
    "site_integration_lock",
)
REVISION_STATUSES = {"bound", "unknown", "not_applicable"}

CI_STATES = {
    "not_configured",
    "unobserved",
    "pending",
    "success",
    "failure",
    "stale",
    "unknown",
}
REVIEW_STATES = {
    "not_requested",
    "requested",
    "pending",
    "evidence_present",
    "incomplete",
    "unknown",
    "unobserved",
}
GATE_STATES = {
    "not_evaluated",
    "pending",
    "passed",
    "failed",
    "unknown",
    "not_applicable",
    "blocked",
}

OBSERVATION_ONLY_FIELDS = frozenset(
    {
        "observed_at",
        "retrieved_at",
        "page_index",
        "page_number",
        "cursor",
        "next_cursor",
        "_observation",
        "observation_timestamp",
    }
)


class ArtifactInputError(ValueError):
    """Raised when an artifact input cannot be safely bound or normalized."""


class RegionOwnershipError(ValueError):
    """Raised when a generated PR-body region is not unambiguously owned."""


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactInputError(f"{name} must be an object")
    return _json_data(dict(value), name)


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactInputError(f"{name} must be a non-empty string")
    return value


def _require_sha(value: Any, name: str) -> str:
    result = _require_string(value, name)
    if FULL_SHA.fullmatch(result) is None:
        raise ArtifactInputError(f"{name} must be a lowercase full Git SHA")
    return result


def _require_bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ArtifactInputError(f"{name} must be a boolean")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ArtifactInputError(f"{name} must be a list")
    return value


def _json_data(value: Any, name: str) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArtifactInputError(f"{name} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ArtifactInputError(f"{name} contains a non-string object key")
            result[key] = _json_data(item, f"{name}.{key}")
        return result
    if isinstance(value, list):
        return [_json_data(item, f"{name}[]") for item in value]
    raise ArtifactInputError(f"{name} must contain JSON data")


def canonical_json(value: Any) -> str:
    """Serialize JSON data without incidental dictionary or whitespace churn."""

    return json.dumps(
        _json_data(value, "value"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def semantic_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _strip_observation_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _strip_observation_metadata(item)
            for key, item in value.items()
            if key not in OBSERVATION_ONLY_FIELDS
        }
    if isinstance(value, list):
        return [_strip_observation_metadata(item) for item in value]
    return value


def _snapshot_content_projection(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Keep evidence identity while removing acquisition/publication churn."""

    projection = copy.deepcopy(dict(snapshot))
    projection.pop("snapshot_digest", None)
    projection.pop("observation", None)
    projection.pop("resume", None)
    surfaces = projection.get("surfaces")
    if isinstance(surfaces, Mapping):
        for surface in surfaces.values():
            if isinstance(surface, dict):
                surface.pop("pages", None)
        metadata = surfaces.get("metadata")
        if isinstance(metadata, Mapping):
            records = metadata.get("records")
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
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
                            REVIEW_REQUEST_MARKER in record["body"]
                            or WORK_CHECKPOINT_MARKER in record["body"]
                        )
                    )
                ]
    normalized = _strip_observation_metadata(projection)
    assert isinstance(normalized, dict)
    return normalized


def _content_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return state that can affect rendered content, excluding observations.

    The current PR body is a concurrency binding for publication, not source
    content for the generated projection.  Keeping it out of this projection
    means a human edit outside the owned region does not churn the generated
    region or review request.
    """

    projection = _strip_observation_metadata(value)
    assert isinstance(projection, dict)
    observed = projection.get("observed")
    if isinstance(observed, dict):
        observed.pop("pr_body", None)
        retrieval = observed.get("retrieval")
        if isinstance(retrieval, Mapping):
            # Keep material completeness and failure state in the semantic
            # identity while removing only acquisition timestamps/cursors.
            observed["retrieval"] = _strip_observation_metadata(retrieval)
        snapshot = observed.get("snapshot")
        if isinstance(snapshot, Mapping):
            observed["snapshot"] = _snapshot_content_projection(snapshot)
    return projection


def _load_sibling(path: str, name: str) -> Any:
    module_path = Path(__file__).with_name(path)
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ArtifactInputError(f"cannot load trusted repository helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise
    return module


def _observer_module() -> Any:
    return _load_sibling("pr_state_observation.py", "templates_pr_state_observation")


def _source_identity(
    value: Any,
    name: str,
    *,
    path: str | None = None,
    require_blob: bool = False,
) -> dict[str, Any]:
    source = _require_object(value, name)
    _require_string(source.get("repository"), f"{name}.repository")
    if source["repository"] != REPOSITORY:
        raise ArtifactInputError(f"{name}.repository must be {REPOSITORY}")
    _require_sha(source.get("revision"), f"{name}.revision")
    actual_path = _require_string(source.get("path"), f"{name}.path")
    if path is not None and actual_path != path:
        raise ArtifactInputError(f"{name}.path must be {path}")
    if require_blob and "blob_sha" not in source:
        raise ArtifactInputError(f"{name}.blob_sha is required for immutable execution")
    if "blob_sha" in source:
        _require_sha(source["blob_sha"], f"{name}.blob_sha")
    if "trusted" in source:
        _require_bool(source["trusted"], f"{name}.trusted")
    elif source.get("authority") == "policy":
        source["trusted"] = True
    if source.get("trusted") is not True:
        raise ArtifactInputError(f"{name} must explicitly identify a trusted source")
    return source


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _read_candidate_file_at_revision(
    repository: str, revision: str, path: str, *, repository_root: Path
) -> dict[str, Any]:
    """Read and verify a file from the immutable candidate commit."""

    if repository != REPOSITORY:
        raise ArtifactInputError("candidate file repository is not the bound repository")
    if _read_git_output(repository_root, "cat-file", "-t", revision) != "commit":
        raise ArtifactInputError("candidate file revision must name a commit object")
    blob_sha = _read_git_output(
        repository_root, "rev-parse", "--verify", f"{revision}:{path}"
    )
    content = _read_git_bytes(repository_root, "show", f"{revision}:{path}")
    if _git_blob_sha(content) != blob_sha:
        raise ArtifactInputError("candidate file blob identity does not match its content")
    return {"sha": blob_sha, "content": content}


class _UniqueYamlLoader(yaml.SafeLoader):
    """Reject duplicate configuration keys instead of silently choosing one."""


def _construct_unique_mapping(
    loader: _UniqueYamlLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ArtifactInputError("candidate configuration contains a duplicate YAML key")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _candidate_toolchain_revision(
    resolved: Mapping[str, Any], *, path: str, field: str
) -> tuple[str, str]:
    """Return the exact configured pin and its verified candidate-file blob."""

    blob_sha = _require_sha(resolved.get("sha"), "candidate configuration blob_sha")
    content = resolved.get("content")
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    elif isinstance(content, bytes):
        content_bytes = content
    else:
        raise ArtifactInputError("candidate configuration content is missing")
    if _git_blob_sha(content_bytes) != blob_sha:
        raise ArtifactInputError("candidate configuration blob identity changed")
    if path != ".agent-policy.yml" or field != "toolchain.revision":
        raise ArtifactInputError(
            "consumer_actual_toolchain verification requires .agent-policy.yml#toolchain.revision"
        )
    try:
        document = yaml.load(content_bytes.decode("utf-8"), Loader=_UniqueYamlLoader)
    except UnicodeDecodeError as exc:
        raise ArtifactInputError("candidate configuration is not UTF-8 YAML") from exc
    except ArtifactInputError:
        raise
    except Exception as exc:
        raise ArtifactInputError(f"candidate configuration is malformed: {exc}") from exc
    current: Any = document
    for part in field.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ArtifactInputError("candidate toolchain.revision is missing")
        current = current[part]
    return _require_sha(current, "candidate toolchain.revision"), blob_sha


def _read_git_output(repository_root: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=repository_root,
            env=environment,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ArtifactInputError("immutable planner source is unavailable") from exc


def _read_git_bytes(repository_root: Path, *arguments: str) -> bytes:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=repository_root,
            env=environment,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ArtifactInputError("immutable planner source is unavailable") from exc


def _verified_planner_content(
    source: Mapping[str, Any],
    *,
    content: bytes | None,
    actual_blob: str | None,
    repository_root: Path,
) -> bytes:
    """Verify planner bytes without importing a mutable checkout helper."""

    declared_blob = source["blob_sha"]
    if content is None:
        if _read_git_output(repository_root, "cat-file", "-t", source["revision"]) != "commit":
            raise ArtifactInputError("planner source revision must name a commit object")
        resolved_blob = _read_git_output(
            repository_root,
            "rev-parse",
            "--verify",
            f"{source['revision']}:{PLANNER_PATH}",
        )
        if resolved_blob != declared_blob:
            raise ArtifactInputError("declared planner blob does not match the immutable commit")
        content = _read_git_bytes(repository_root, "show", f"{source['revision']}:{PLANNER_PATH}")
    computed_blob = _git_blob_sha(content)
    if actual_blob is not None and actual_blob != computed_blob:
        raise ArtifactInputError("transport planner blob does not match its content")
    if computed_blob != declared_blob:
        raise ArtifactInputError("declared planner blob does not match planner content")
    return content


def execute_bound_planner(
    source: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    content: bytes | None = None,
    actual_blob: str | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Execute only planner bytes proven to match ``planner.source``.

    Local normalization reads the source from the exact Git commit. Live
    publication supplies bytes fetched from the provider at that same full
    commit SHA. Neither path may execute the candidate checkout's sibling
    planner.
    """

    normalized_source = _source_identity(
        source, "planner.source", path=PLANNER_PATH, require_blob=True
    )
    try:
        planner_content = _verified_planner_content(
            normalized_source,
            content=content,
            actual_blob=actual_blob,
            repository_root=repository_root or Path(__file__).parents[3],
        )
        namespace: dict[str, Any] = {
            "__file__": f"{normalized_source['revision']}:{PLANNER_PATH}",
            "__name__": "templates_bound_review_planner",
        }
        exec(compile(planner_content, namespace["__file__"], "exec"), namespace)
        planner = namespace.get("plan")
        if not callable(planner):
            raise ArtifactInputError("verified planner source does not expose plan(packet)")
        result = planner(dict(packet))
    except ArtifactInputError:
        raise
    except Exception as exc:
        raise ArtifactInputError(
            f"immutable planner source could not be loaded or executed: {exc}"
        ) from exc
    if not isinstance(result, Mapping):
        raise ArtifactInputError("immutable planner returned a non-object result")
    return _json_data(dict(result), "planner result")


def _normalize_pull_request(candidate: dict[str, Any]) -> dict[str, Any]:
    raw = candidate.get("pull_request", candidate.get("pr"))
    pull_request = _require_object(raw, "candidate.pull_request")
    number = pull_request.get("number")
    if type(number) is not int or number <= 0:
        raise ArtifactInputError("candidate.pull_request.number must be positive")
    _require_string(pull_request.get("id"), "candidate.pull_request.id")
    if "url" in pull_request:
        _require_string(pull_request["url"], "candidate.pull_request.url")
    if "body_revision" in pull_request:
        _require_string(pull_request["body_revision"], "candidate.pull_request.body_revision")
    return pull_request


def _provider_identifier(value: Any, name: str) -> str:
    if type(value) is int and value > 0:
        return str(value)
    return _require_string(value, name)


def _normalize_provider_identity(value: Any, name: str) -> dict[str, Any]:
    identity = _require_object(value, name)
    return {
        "provider": _require_string(identity.get("provider"), f"{name}.provider"),
        "repository_id": _provider_identifier(
            identity.get("repository_id"), f"{name}.repository_id"
        ),
        "resource_id": _provider_identifier(identity.get("resource_id"), f"{name}.resource_id"),
    }


def _provider_identity_key(identity: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(identity["provider"]),
        str(identity["repository_id"]),
        str(identity["resource_id"]),
    )


def candidate_member_binding_digest(candidate: Mapping[str, Any]) -> str:
    """Identify the ordered member bindings used by stack-bound evidence."""

    members = candidate.get("members")
    if not isinstance(members, list):
        raise ArtifactInputError("candidate.members must be a list")
    projection: list[dict[str, Any]] = []
    for index, member in enumerate(members):
        if not isinstance(member, Mapping):
            raise ArtifactInputError(f"candidate.members[{index}] must be an object")
        pull_request = member.get("pull_request")
        if not isinstance(pull_request, Mapping):
            raise ArtifactInputError(
                f"candidate.members[{index}].pull_request must be an object"
            )
        provider_identity = pull_request.get("provider_identity")
        if not isinstance(provider_identity, Mapping):
            raise ArtifactInputError(
                f"candidate.members[{index}].pull_request.provider_identity must be an object"
            )
        projection.append(
            {
                "id": member.get("id"),
                "authority": member.get("authority"),
                "base_sha": member.get("base_sha"),
                "head_sha": member.get("head_sha"),
                "pull_request": {
                    "number": pull_request.get("number"),
                    "provider_identity": {
                        "provider": provider_identity.get("provider"),
                        "repository_id": str(provider_identity.get("repository_id")),
                        "resource_id": str(provider_identity.get("resource_id")),
                    },
                    "provider_path": pull_request.get("provider_path"),
                },
            }
        )
    return semantic_digest(projection)


def _normalize_candidate(source: dict[str, Any]) -> dict[str, Any]:
    raw = _require_object(source.get("candidate"), "candidate")
    candidate = copy.deepcopy(raw)
    repository = _require_string(candidate.get("repository"), "candidate.repository")
    if repository != REPOSITORY or source.get("repository") != repository:
        raise ArtifactInputError("candidate.repository must match the templates repository")
    _require_string(candidate.get("authority"), "candidate.authority")
    _require_string(candidate.get("branch"), "candidate.branch")
    _require_sha(candidate.get("base_sha"), "candidate.base_sha")
    _require_sha(candidate.get("effective_base_sha"), "candidate.effective_base_sha")
    head_sha = _require_sha(candidate.get("head_sha"), "candidate.head_sha")
    members = _require_list(candidate.get("members"), "candidate.members")
    if not members:
        raise ArtifactInputError("candidate.members must not be empty")
    seen: set[str] = set()
    seen_pr_numbers: set[int] = set()
    seen_provider_identities: set[tuple[str, str, str]] = set()
    normalized_members: list[dict[str, Any]] = []
    for index, raw_member in enumerate(members):
        member = _require_object(raw_member, f"candidate.members[{index}]")
        member_id = _require_string(member.get("id"), f"candidate.members[{index}].id")
        if member_id in seen:
            raise ArtifactInputError("candidate member IDs must be unique")
        seen.add(member_id)
        _require_string(member.get("authority"), f"candidate.members[{index}].authority")
        _require_sha(member.get("base_sha"), f"candidate.members[{index}].base_sha")
        _require_sha(member.get("head_sha"), f"candidate.members[{index}].head_sha")
        member_pr = _require_object(
            member.get("pull_request"), f"candidate.members[{index}].pull_request"
        )
        member_number = member_pr.get("number")
        if type(member_number) is not int or member_number <= 0:
            raise ArtifactInputError(
                f"candidate.members[{index}].pull_request.number must be positive"
            )
        if member_number in seen_pr_numbers:
            raise ArtifactInputError("candidate member pull-request numbers must be unique")
        seen_pr_numbers.add(member_number)
        provider_identity = _normalize_provider_identity(
            member_pr.get("provider_identity"),
            f"candidate.members[{index}].pull_request.provider_identity",
        )
        provider_key = _provider_identity_key(provider_identity)
        if provider_key in seen_provider_identities:
            raise ArtifactInputError("candidate member provider identities must be unique")
        seen_provider_identities.add(provider_key)
        provider_path = _require_string(
            member_pr.get("provider_path", f"/repos/{repository}/pulls/{member_number}"),
            f"candidate.members[{index}].pull_request.provider_path",
        )
        member["pull_request"] = {
            **member_pr,
            "number": member_number,
            "provider_identity": provider_identity,
            "provider_path": provider_path,
        }
        normalized_members.append(member)
    candidate["members"] = normalized_members
    pull_request = _normalize_pull_request(candidate)
    candidate["pull_request"] = pull_request
    candidate.pop("pr", None)
    target_members = [
        member
        for member in normalized_members
        if member["pull_request"]["number"] == pull_request["number"]
    ]
    if len(target_members) != 1:
        raise ArtifactInputError(
            "candidate.members must identify the target pull request exactly once"
        )
    target_member = target_members[0]
    if target_member["head_sha"] != head_sha:
        raise ArtifactInputError("target member head must match candidate.head_sha")
    if target_member["base_sha"] != candidate["base_sha"]:
        raise ArtifactInputError("target member base must match candidate.base_sha")
    target_identity = target_member["pull_request"]["provider_identity"]
    declared_identity = pull_request.get("provider_identity")
    if declared_identity is not None:
        normalized_identity = _normalize_provider_identity(
            declared_identity, "candidate.pull_request.provider_identity"
        )
        if _provider_identity_key(normalized_identity) != _provider_identity_key(target_identity):
            raise ArtifactInputError(
                "candidate.pull_request provider identity does not match target member"
            )
        pull_request["provider_identity"] = normalized_identity
    else:
        pull_request["provider_identity"] = copy.deepcopy(target_identity)
    if pull_request.get("head_sha") is not None and pull_request["head_sha"] != head_sha:
        raise ArtifactInputError(
            "candidate.pull_request.head_sha does not match candidate.head_sha"
        )
    if (
        pull_request.get("base_sha") is not None
        and pull_request["base_sha"] != candidate["base_sha"]
    ):
        raise ArtifactInputError(
            "candidate.pull_request.base_sha does not match candidate.base_sha"
        )
    return candidate


def _normalize_revision_bindings(
    source: dict[str, Any],
    candidate: dict[str, Any],
    *,
    candidate_file_resolver: Callable[[str, str, str], Mapping[str, Any]] | None = None,
    repository_root: Path | None = None,
) -> tuple[list[dict[str, Any]], str]:
    raw_bindings = _require_list(source.get("revision_bindings"), "revision_bindings")
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_bindings):
        binding = _require_object(raw, f"revision_bindings[{index}]")
        role = _require_string(binding.get("role"), f"revision_bindings[{index}].role")
        if role not in REVISION_ROLES:
            raise ArtifactInputError(
                f"revision_bindings[{index}].role must be one of {', '.join(REVISION_ROLES)}"
            )
        if role in seen:
            raise ArtifactInputError(f"revision binding role is duplicated: {role}")
        seen.add(role)
        status = _require_string(binding.get("status"), f"revision_bindings[{index}].status")
        if status not in REVISION_STATUSES:
            raise ArtifactInputError(f"revision_bindings[{index}].status is invalid")
        normalized = {
            "role": role,
            "status": status,
            "label": _require_string(
                binding.get("label", role.replace("_", " ")),
                f"revision_bindings[{index}].label",
            ),
        }
        if status == "bound":
            normalized["revision"] = _require_sha(
                binding.get("revision"), f"revision_bindings[{index}].revision"
            )
            normalized["source"] = _require_object(
                binding.get("source"), f"revision_bindings[{index}].source"
            )
            _require_string(
                normalized["source"].get("locator"),
                f"revision_bindings[{index}].source.locator",
            )
        elif binding.get("revision") is not None:
            raise ArtifactInputError(
                f"revision_bindings[{index}].revision must be absent for {status}"
            )
        if status != "bound" and "reason" in binding:
            normalized["reason"] = _require_string(
                binding["reason"], f"revision_bindings[{index}].reason"
            )
        if role == "consumer_actual_toolchain" and status == "bound":
            actual_source = normalized["source"]
            source_candidate_head = _require_sha(
                actual_source.get("candidate_head_sha"),
                f"revision_bindings[{index}].source.candidate_head_sha",
            )
            if source_candidate_head != candidate["head_sha"]:
                raise ArtifactInputError(
                    "consumer_actual_toolchain must be read at the target candidate head"
                )
            worktree_head = actual_source.get("worktree_head_sha")
            if (
                worktree_head is not None
                and _require_sha(
                    worktree_head, f"revision_bindings[{index}].source.worktree_head_sha"
                )
                != candidate["head_sha"]
            ):
                raise ArtifactInputError(
                    "consumer_actual_toolchain source is bound to an unrelated worktree head"
                )
            _require_string(
                actual_source.get("path"),
                f"revision_bindings[{index}].source.path",
            )
            _require_string(
                actual_source.get("field"),
                f"revision_bindings[{index}].source.field",
            )
            path = actual_source["path"]
            field = actual_source["field"]
            if path != ".agent-policy.yml" or field != "toolchain.revision":
                raise ArtifactInputError(
                    "consumer_actual_toolchain verification requires "
                    ".agent-policy.yml#toolchain.revision"
                )
            declared_blob = _require_sha(
                actual_source.get("blob_sha"),
                f"revision_bindings[{index}].source.blob_sha",
            )
            resolver = candidate_file_resolver
            if resolver is None:
                root = repository_root or Path(__file__).parents[3]

                def resolver(
                    repository: str,
                    revision: str,
                    candidate_path: str,
                    *,
                    _root: Path = root,
                ) -> Mapping[str, Any]:
                    return _read_candidate_file_at_revision(
                        repository,
                        revision,
                        candidate_path,
                        repository_root=_root,
                    )

            try:
                resolved_file = resolver(
                    candidate["repository"], candidate["head_sha"], path
                )
                if not isinstance(resolved_file, Mapping):
                    raise ArtifactInputError(
                        "consumer_actual_toolchain resolved candidate file must be an object"
                    )
                actual_revision, actual_blob = _candidate_toolchain_revision(
                    resolved_file,
                    path=path,
                    field=field,
                )
            except ArtifactInputError:
                raise
            except Exception as exc:
                raise ArtifactInputError(
                    "consumer_actual_toolchain could not be read from the exact candidate"
                ) from exc
            if actual_blob != declared_blob:
                raise ArtifactInputError(
                    "consumer_actual_toolchain candidate configuration blob binding changed"
                )
            if actual_revision != normalized["revision"]:
                raise ArtifactInputError(
                    "consumer_actual_toolchain claim differs from the exact candidate configuration"
                )
        bindings.append(normalized)
    missing_roles = [role for role in REVISION_ROLES if role not in seen]
    if missing_roles:
        raise ArtifactInputError(
            "revision_bindings must explicitly declare every role: "
            + ", ".join(missing_roles)
        )
    bindings.sort(key=lambda item: item["role"])
    return bindings, semantic_digest(bindings)


def _trusted_planner_source(
    bindings: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    *,
    trusted_base_sha: str,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Return the independently bound immutable source for planner execution.

    ``planner.source`` is executable input, so its ``trusted`` flag cannot be
    its own authority.  The role-labelled maintainer binding is the separate
    trust anchor that authenticates the repository, revision, path, and blob
    identity used for the planner.
    """

    trusted_base_sha = _require_sha(trusted_base_sha, "trusted_base_sha")
    if candidate["base_sha"] != trusted_base_sha:
        raise ArtifactInputError(
            "candidate.base_sha does not match the independently trusted base"
        )
    root = repository_root or Path(__file__).parents[3]
    try:
        manifest = json.loads(
            _read_git_bytes(
                root,
                "show",
                f"{trusted_base_sha}:{TRUSTED_SOURCE_MANIFEST_PATH}",
            ).decode("utf-8")
        )
    except (ArtifactInputError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactInputError(
            "trusted planner source manifest is unavailable at the candidate base"
        ) from exc
    if not isinstance(manifest, Mapping):
        raise ArtifactInputError("trusted planner source manifest must be an object")
    if manifest.get("schema_version") != 2:
        raise ArtifactInputError("trusted planner source manifest has an unsupported schema")
    if manifest.get("kind") != "repository-maintainer-skill-reference":
        raise ArtifactInputError("trusted planner source manifest has an invalid kind")
    if manifest.get("repository") != REPOSITORY:
        raise ArtifactInputError("trusted planner source manifest has an invalid repository")
    manifest_revision = _require_sha(
        manifest.get("revision"), "trusted planner source manifest.revision"
    )
    manifest_path = _require_string(
        manifest.get("path"), "trusted planner source manifest.path"
    )
    manifest_blob = _require_sha(
        manifest.get("blob_sha"), "trusted planner source manifest.blob_sha"
    )
    if manifest_path != "repository-skills/land-templates-stack/SKILL.md":
        raise ArtifactInputError("trusted planner source manifest path is not canonical")
    if _read_git_output(root, "cat-file", "-t", manifest_revision) != "commit":
        raise ArtifactInputError("trusted planner source manifest revision is not a commit")
    if (
        _read_git_output(root, "rev-parse", "--verify", f"{manifest_revision}:{manifest_path}")
        != manifest_blob
    ):
        raise ArtifactInputError("trusted planner source manifest Skill blob is not current")

    closure = manifest.get("closure")
    if not isinstance(closure, list):
        raise ArtifactInputError("trusted planner source manifest closure is missing")
    closure_by_path: dict[str, str] = {}
    for index, item in enumerate(closure):
        if not isinstance(item, Mapping):
            raise ArtifactInputError(f"trusted planner source closure entry {index} is invalid")
        path = _require_string(item.get("path"), f"trusted planner source closure[{index}].path")
        blob = _require_sha(
            item.get("blob_sha"), f"trusted planner source closure[{index}].blob_sha"
        )
        if path in closure_by_path:
            raise ArtifactInputError("trusted planner source closure contains a duplicate path")
        closure_by_path[path] = blob
        if _read_git_output(root, "rev-parse", "--verify", f"{manifest_revision}:{path}") != blob:
            raise ArtifactInputError(f"trusted planner source closure is not current: {path}")
    trusted_blob = closure_by_path.get(PLANNER_PATH)
    if trusted_blob is None:
        raise ArtifactInputError("trusted planner source closure omits the planner")

    expected_source = {
        "repository": REPOSITORY,
        "revision": manifest_revision,
        "path": PLANNER_PATH,
        "blob_sha": trusted_blob,
        "trusted": True,
    }
    binding = next(
        (item for item in bindings if item.get("role") == "trusted_maintainer_source"),
        None,
    )
    if not isinstance(binding, Mapping) or binding.get("status") != "bound":
        raise ArtifactInputError(
            "trusted_maintainer_source must be bound to authenticate planner.source"
        )
    source = _source_identity(
        binding.get("source"),
        "trusted_maintainer_source.source",
        path=PLANNER_PATH,
        require_blob=True,
    )
    if binding.get("revision") != source["revision"] or any(
        source.get(field) != expected_source[field]
        for field in ("repository", "revision", "path", "blob_sha")
    ):
        raise ArtifactInputError(
            "trusted_maintainer_source is not bound to the installed immutable source closure"
        )
    return expected_source


def _require_trusted_planner_source(
    planner_source: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    *,
    trusted_base_sha: str,
) -> dict[str, Any]:
    trusted_source = _trusted_planner_source(
        bindings, candidate, trusted_base_sha=trusted_base_sha
    )
    for field in ("repository", "revision", "path", "blob_sha"):
        if planner_source.get(field) != trusted_source.get(field):
            raise ArtifactInputError(
                "planner.source is not bound to the trusted_maintainer_source "
                f"{field}"
            )
    return trusted_source


def _planner_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(candidate[key])
        for key in (
            "repository",
            "authority",
            "base_sha",
            "effective_base_sha",
            "head_sha",
            "members",
        )
        if key in candidate
    }
    if "integration_base_tree_sha" in candidate:
        result["integration_base_tree_sha"] = candidate["integration_base_tree_sha"]
    return result


def _planner_packet(
    source: dict[str, Any],
    candidate: dict[str, Any],
    planner_input_binding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    planner_input = _require_object(source.get("planner"), "planner")
    planner_source = _source_identity(
        planner_input.get("source"), "planner.source", path=PLANNER_PATH
    )
    raw_packet = planner_input.get("packet", planner_input.get("input"))
    if raw_packet is None:
        packet = {
            "schema_version": PLANNER_SCHEMA_VERSION,
            "objective": source["objective"],
            "purpose": source["purpose"],
            "contract": copy.deepcopy(source["contract"]),
            "candidate": _planner_candidate(candidate),
            "change": copy.deepcopy(source["change"]),
            "input_binding": copy.deepcopy(planner_input_binding),
            "preflight": copy.deepcopy(planner_input.get("preflight")),
            "reviews": copy.deepcopy(planner_input.get("reviews", [])),
            "requests": copy.deepcopy(planner_input.get("requests", [])),
            "discovery": copy.deepcopy(planner_input.get("discovery")),
            "options": copy.deepcopy(planner_input.get("options", {})),
        }
    else:
        packet = _require_object(raw_packet, "planner.packet")
        expected = {
            "schema_version": PLANNER_SCHEMA_VERSION,
            "objective": source["objective"],
            "purpose": source["purpose"],
            "contract": source["contract"],
            "candidate": _planner_candidate(candidate),
            "change": source["change"],
            "input_binding": planner_input_binding,
        }
        for key, expected_value in expected.items():
            if key not in packet or semantic_digest(packet[key]) != semantic_digest(expected_value):
                raise ArtifactInputError(
                    f"planner.packet.{key} is not bound to the structured input"
                )
    packet = _json_data(packet, "planner.packet")
    try:
        result = execute_bound_planner(planner_source, packet)
    except ArtifactInputError as exc:
        raise ArtifactInputError(f"existing review-scope planner rejected input: {exc}") from exc
    declared_result = planner_input.get("result")
    if declared_result is not None:
        declared = _json_data(declared_result, "planner.result")
        if semantic_digest(declared) != semantic_digest(result):
            raise ArtifactInputError("planner.result does not match the existing planner output")
    return planner_source, packet, result


def _normalize_gate(
    source: dict[str, Any],
    candidate: dict[str, Any],
    revision_digest: str,
    planner_packet: dict[str, Any],
    planner_result: dict[str, Any],
) -> dict[str, Any]:
    raw_gate = _require_object(source.get("gate"), "gate")
    status = _require_string(raw_gate.get("status"), "gate.status")
    if status not in GATE_STATES:
        raise ArtifactInputError(f"gate.status must be one of {sorted(GATE_STATES)}")
    gate = copy.deepcopy(raw_gate)
    gate["source"] = _source_identity(gate.get("source"), "gate.source")
    binding = _require_object(gate.get("input_binding"), "gate.input_binding")
    declared_digest = _require_string(gate.get("input_binding_digest"), "gate.input_binding_digest")
    if declared_digest != semantic_digest(binding):
        raise ArtifactInputError("gate.input_binding_digest does not match gate.input_binding")
    expected = {
        "repository": REPOSITORY,
        "pull_request_id": candidate["pull_request"]["id"],
        "candidate_head_sha": candidate["head_sha"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "revision_bindings_digest": revision_digest,
        "planner_input_digest": semantic_digest(planner_packet),
        "planner_result_digest": semantic_digest(planner_result),
    }
    for key, expected_value in expected.items():
        if binding.get(key) != expected_value:
            raise ArtifactInputError(f"gate.input_binding.{key} is not current")
    gate["input_binding"] = binding
    return gate


def _normalize_observation(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    observed = _require_object(source.get("observed"), "observed")
    _require_bool(observed.get("complete"), "observed.complete")
    _require_string(observed.get("source"), "observed.source")
    _require_string(observed.get("observed_at"), "observed.observed_at")
    facts = _require_object(observed.get("facts", {}), "observed.facts")
    result = copy.deepcopy(observed)
    result["facts"] = facts
    retrieval = result.get("retrieval")
    if retrieval is not None:
        retrieval = _require_object(retrieval, "observed.retrieval")
        if "complete" in retrieval:
            _require_bool(retrieval["complete"], "observed.retrieval.complete")
        result["retrieval"] = retrieval
    snapshot = result.get("snapshot")
    if snapshot is not None:
        try:
            _observer_module().validate_snapshot(_require_object(snapshot, "observed.snapshot"))
        except Exception as exc:
            raise ArtifactInputError(f"observed.snapshot is invalid: {exc}") from exc
        snapshot_candidate = snapshot["candidate"]
        expected = {
            "repository": candidate["repository"],
            "number": candidate["pull_request"]["number"],
            "expected_head_sha": candidate["head_sha"],
            "expected_base_sha": candidate["base_sha"],
        }
        for key, expected_value in expected.items():
            if snapshot_candidate.get(key) != expected_value:
                raise ArtifactInputError(
                    f"observed.snapshot.candidate.{key} is not bound to candidate"
                )
    pr_body = result.get("pr_body")
    if pr_body is not None:
        pr_body = _require_object(pr_body, "observed.pr_body")
        body = pr_body.get("body")
        _require_string(body, "observed.pr_body.body")
        revision = _require_string(pr_body.get("revision"), "observed.pr_body.revision")
        declared_body_digest = pr_body.get("body_digest")
        actual_body_digest = semantic_digest(body)
        if declared_body_digest is not None and declared_body_digest != actual_body_digest:
            raise ArtifactInputError("observed.pr_body.body_digest does not match body")
        pr_body["body_digest"] = actual_body_digest
        pr_body["revision"] = revision
        result["pr_body"] = pr_body
    _validate_ci(facts.get("ci"), candidate)
    _validate_review_state(facts.get("review"))
    return result


def _validate_ci(raw_ci: Any, candidate: dict[str, Any]) -> None:
    if raw_ci is None:
        return
    ci = _require_object(raw_ci, "observed.facts.ci")
    state = _require_string(ci.get("status"), "observed.facts.ci.status")
    if state not in CI_STATES:
        raise ArtifactInputError(f"observed.facts.ci.status must be one of {sorted(CI_STATES)}")
    if state in {"success", "failure", "stale"}:
        _require_sha(ci.get("head_sha"), "observed.facts.ci.head_sha")
    applicable = ci.get("applicable_to")
    if applicable is not None:
        applicable = _require_object(applicable, "observed.facts.ci.applicable_to")
        if "head_sha" in applicable:
            _require_sha(applicable["head_sha"], "observed.facts.ci.applicable_to.head_sha")
        if "base_sha" in applicable:
            _require_sha(applicable["base_sha"], "observed.facts.ci.applicable_to.base_sha")
        if "effective_base_sha" in applicable:
            _require_sha(
                applicable["effective_base_sha"],
                "observed.facts.ci.applicable_to.effective_base_sha",
            )
        if "candidate_members_digest" in applicable:
            member_digest = _require_string(
                applicable["candidate_members_digest"],
                "observed.facts.ci.applicable_to.candidate_members_digest",
            )
            if re.fullmatch(r"[0-9a-f]{64}", member_digest) is None:
                raise ArtifactInputError(
                    "observed.facts.ci.applicable_to.candidate_members_digest "
                    "must be a lowercase SHA-256 digest"
                )
    attempt = ci.get("attempt")
    if attempt is not None and (type(attempt) is not int or attempt <= 0):
        raise ArtifactInputError("observed.facts.ci.attempt must be a positive integer")


def _validate_review_state(raw_review: Any) -> None:
    if raw_review is None:
        return
    review = _require_object(raw_review, "observed.facts.review")
    state = _require_string(review.get("status"), "observed.facts.review.status")
    if state not in REVIEW_STATES:
        raise ArtifactInputError(
            f"observed.facts.review.status must be one of {sorted(REVIEW_STATES)}"
        )


def _normalize_judgments(source: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    raw_judgments = _require_list(source.get("judgments", []), "judgments")
    judgments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_judgments):
        judgment = _require_object(raw, f"judgments[{index}]")
        identifier = _require_string(judgment.get("id"), f"judgments[{index}].id")
        if identifier in seen:
            raise ArtifactInputError("judgment IDs must be unique")
        seen.add(identifier)
        disposition = _require_string(
            judgment.get("disposition"), f"judgments[{index}].disposition"
        )
        if disposition not in {"valid", "invalid", "resolved", "deferred", "next_action"}:
            raise ArtifactInputError(f"judgments[{index}].disposition is invalid")
        actor = _require_object(judgment.get("actor"), f"judgments[{index}].actor")
        _require_string(actor.get("kind"), f"judgments[{index}].actor.kind")
        _require_string(actor.get("id"), f"judgments[{index}].actor.id")
        _require_string(judgment.get("finding_ref"), f"judgments[{index}].finding_ref")
        _require_string(judgment.get("rationale"), f"judgments[{index}].rationale")
        _require_string(judgment.get("judged_at"), f"judgments[{index}].judged_at")
        if judgment.get("candidate_head_sha") != candidate["head_sha"]:
            raise ArtifactInputError(f"judgments[{index}] is not bound to candidate.head_sha")
        for field in ("base_sha", "effective_base_sha"):
            if judgment.get(field) != candidate[field]:
                raise ArtifactInputError(f"judgments[{index}] is not bound to candidate.{field}")
        evidence_refs = _require_list(
            judgment.get("evidence_refs", []), f"judgments[{index}].evidence_refs"
        )
        if any(not isinstance(item, str) or not item.strip() for item in evidence_refs):
            raise ArtifactInputError(f"judgments[{index}].evidence_refs must contain strings")
        normalized = copy.deepcopy(judgment)
        normalized["actor"] = actor
        normalized["evidence_refs"] = sorted(set(evidence_refs))
        judgments.append(normalized)
    judgments.sort(key=lambda item: item["id"])
    return judgments


def _normalize_work(source: dict[str, Any]) -> dict[str, Any]:
    work = _require_object(source.get("work"), "work")
    normalized = copy.deepcopy(work)
    _require_string(normalized.get("objective_ref"), "work.objective_ref")
    _require_string(normalized.get("next_safe_action"), "work.next_safe_action")
    _require_string(normalized.get("stopping_boundary"), "work.stopping_boundary")
    for field in ("blockers", "unresolved_finding_refs"):
        values = _require_list(normalized.get(field, []), f"work.{field}")
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise ArtifactInputError(f"work.{field} must contain non-empty strings")
        normalized[field] = sorted(set(values))
    for forbidden in ("findings", "full_findings", "transcript", "source_text"):
        if forbidden in normalized:
            raise ArtifactInputError(f"work.{forbidden} is not allowed; use references instead")
    diagnostic_fields = (
        "failure_scope",
        "current_failure_scope",
        "evidence_gap",
        "attempted_paths",
        "invalidated_paths",
        "retry_conditions",
        "current_hypothesis",
        "current_strategy",
        "strategy_attempt_count",
        "exhausted_strategies",
        "strategy_switch_reason",
        "diagnostic_budget",
        "progress_frontier",
        "last_material_progress",
        "external_wait",
        "diagnostic_state",
    )
    list_fields = {
        "attempted_paths",
        "invalidated_paths",
        "retry_conditions",
        "exhausted_strategies",
    }
    for field in diagnostic_fields:
        if field not in normalized:
            continue
        value = _json_data(normalized[field], f"work.{field}")
        if field in list_fields and not isinstance(value, list):
            raise ArtifactInputError(f"work.{field} must be a list")
        if field == "strategy_attempt_count" and (
            type(value) is not int or value < 0
        ):
            raise ArtifactInputError("work.strategy_attempt_count must be a non-negative integer")
        normalized[field] = value
    closure_audit = normalized.get("closure_audit")
    if closure_audit is not None:
        if not isinstance(closure_audit, list):
            raise ArtifactInputError("work.closure_audit must be a list")
        normalized_closure: list[dict[str, Any]] = []
        seen_families: set[str] = set()
        for index, raw_item in enumerate(closure_audit):
            item = _require_object(raw_item, f"work.closure_audit[{index}]")
            family = _require_string(
                item.get("family"), f"work.closure_audit[{index}].family"
            )
            if family in seen_families:
                raise ArtifactInputError("work.closure_audit families must be unique")
            seen_families.add(family)
            status = _require_string(
                item.get("status"), f"work.closure_audit[{index}].status"
            )
            if status not in {"closed", "gap", "deliberately_untested"}:
                raise ArtifactInputError(
                    "work.closure_audit status must be closed, gap, or deliberately_untested"
                )
            evidence = _require_list(
                item.get("evidence", []), f"work.closure_audit[{index}].evidence"
            )
            if any(not isinstance(value, str) or not value.strip() for value in evidence):
                raise ArtifactInputError(
                    f"work.closure_audit[{index}].evidence must contain strings"
                )
            gaps = _require_list(
                item.get("gaps", []), f"work.closure_audit[{index}].gaps"
            )
            if any(not isinstance(value, str) or not value.strip() for value in gaps):
                raise ArtifactInputError(
                    f"work.closure_audit[{index}].gaps must contain strings"
                )
            normalized_closure.append(
                {
                    "family": family,
                    "status": status,
                    "evidence": sorted(set(evidence)),
                    "gaps": sorted(set(gaps)),
                }
            )
        normalized["closure_audit"] = sorted(
            normalized_closure, key=lambda item: item["family"]
        )
    return normalized


def _optional_binding_consistency(
    input_binding: dict[str, Any],
    candidate: dict[str, Any],
    revision_digest: str,
) -> None:
    aliases = {
        "candidate_head_sha": candidate["head_sha"],
        "head_sha": candidate["head_sha"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "revision_bindings_digest": revision_digest,
    }
    for key, expected in aliases.items():
        if key in input_binding and input_binding[key] != expected:
            raise ArtifactInputError(f"input_binding.{key} is not current")


def _artifact_binding(
    source: dict[str, Any],
    candidate: dict[str, Any],
    revision_digest: str,
    planner_source: Mapping[str, Any],
) -> dict[str, Any]:
    pull_request = candidate["pull_request"]
    return {
        "repository": candidate["repository"],
        "pull_request_id": pull_request["id"],
        "pull_request_number": pull_request["number"],
        "authority": candidate["authority"],
        "branch": candidate["branch"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "candidate_head_sha": candidate["head_sha"],
        "revision_bindings_digest": revision_digest,
        "planner_source": copy.deepcopy(dict(planner_source)),
        "input_binding": copy.deepcopy(source["input_binding"]),
    }


class NormalizedReviewArtifacts:
    """A validated, planner-bound structured source of truth."""

    __slots__ = (
        "data",
        "planner_packet",
        "planner_result",
        "semantic_digest",
        "binding_digest",
        "observation_digest",
        "blockers",
    )

    def __init__(
        self,
        data: dict[str, Any],
        planner_packet: dict[str, Any],
        planner_result: dict[str, Any],
        semantic_digest_value: str,
        binding_digest: str,
        observation_digest: str,
        blockers: tuple[str, ...],
    ) -> None:
        self.data = data
        self.planner_packet = planner_packet
        self.planner_result = planner_result
        self.semantic_digest = semantic_digest_value
        self.binding_digest = binding_digest
        self.observation_digest = observation_digest
        self.blockers = blockers

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)


def review_projection_digest(normalized: NormalizedReviewArtifacts) -> str:
    """Identify request/body content without durable resume state."""

    projection = _content_projection(normalized.data)
    projection.pop("work", None)
    return semantic_digest(projection)


def normalize(
    source: Mapping[str, Any],
    *,
    trusted_base_sha: str,
    candidate_file_resolver: Callable[[str, str, str], Mapping[str, Any]] | None = None,
    repository_root: Path | None = None,
) -> NormalizedReviewArtifacts:
    """Validate and bind the structured input to the existing planner.

    Normalization never converts an incomplete observation or a prose claim
    into a successful gate.  Such conditions remain visible in ``blockers``
    while the planner's own result is preserved verbatim.
    """

    raw = _require_object(source, "input")
    if raw.get("kind") != INPUT_KIND:
        raise ArtifactInputError(f"input.kind must be {INPUT_KIND}")
    if raw.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise ArtifactInputError("unsupported review-artifacts input schema")
    repository = _require_string(raw.get("repository"), "repository")
    if repository != REPOSITORY:
        raise ArtifactInputError(f"repository must be {REPOSITORY}")
    _require_string(raw.get("objective"), "objective")
    purpose = _require_string(raw.get("purpose"), "purpose")
    contract = _require_object(raw.get("contract"), "contract")
    change = _require_object(raw.get("change"), "change")
    input_binding = _require_object(raw.get("input_binding"), "input_binding")
    candidate = _normalize_candidate(raw)
    trusted_base_sha = _require_sha(trusted_base_sha, "trusted_base_sha")
    revisions, revision_digest = _normalize_revision_bindings(
        raw,
        candidate,
        candidate_file_resolver=candidate_file_resolver,
        repository_root=repository_root,
    )
    _optional_binding_consistency(input_binding, candidate, revision_digest)
    planner_input = _require_object(raw.get("planner"), "planner")
    planner_source = _source_identity(
        planner_input.get("source"), "planner.source", path=PLANNER_PATH, require_blob=True
    )
    _require_trusted_planner_source(
        planner_source,
        revisions,
        candidate,
        trusted_base_sha=trusted_base_sha,
    )
    planner_binding = {
        **copy.deepcopy(input_binding),
        "artifact_binding": _artifact_binding(
            raw, candidate, revision_digest, planner_source
        ),
        "planner_source": copy.deepcopy(planner_source),
    }
    planner_source, planner_packet, planner_result = _planner_packet(
        {**raw, "contract": contract, "change": change, "purpose": purpose},
        candidate,
        planner_binding,
    )
    observation = _normalize_observation(raw, candidate)
    gate = _normalize_gate(raw, candidate, revision_digest, planner_packet, planner_result)
    judgments = _normalize_judgments(raw, candidate)
    work = _normalize_work(raw)
    normalized = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "kind": INPUT_KIND,
        "repository": repository,
        "objective": raw["objective"],
        "purpose": purpose,
        "contract": contract,
        "candidate": candidate,
        "change": change,
        "input_binding": input_binding,
        "trusted_base_sha": trusted_base_sha,
        "revision_bindings": revisions,
        "planner": {
            "source": planner_source,
            "packet": planner_packet,
            "result": planner_result,
        },
        "observed": observation,
        "gate": gate,
        "judgments": judgments,
        "work": work,
    }
    semantic_projection = _content_projection(normalized)
    content_digest = semantic_digest(semantic_projection)
    binding_projection = {
        "candidate": candidate,
        "trusted_base_sha": trusted_base_sha,
        "revision_bindings": revisions,
        "planner_source": planner_source,
        "planner_packet": planner_packet,
        "planner_result": planner_result,
        "gate_input_binding": gate["input_binding"],
    }
    binding_digest = semantic_digest(binding_projection)
    observation_digest = semantic_digest(observation)
    blockers = _blocking_reasons(normalized, planner_result)
    return NormalizedReviewArtifacts(
        normalized,
        planner_packet,
        planner_result,
        content_digest,
        binding_digest,
        observation_digest,
        tuple(blockers),
    )


def _blocking_reasons(data: dict[str, Any], planner_result: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    observed = data["observed"]
    if not observed["complete"]:
        blockers.append("observation_incomplete")
    retrieval = observed.get("retrieval")
    if isinstance(retrieval, dict) and retrieval.get("complete") is False:
        blockers.append("observation_retrieval_incomplete")
    snapshot = observed.get("snapshot")
    if isinstance(snapshot, dict):
        if snapshot.get("complete") is not True:
            blockers.append("observation_snapshot_incomplete")
        if snapshot.get("binding_status") != "stable":
            blockers.append("observation_snapshot_binding_not_stable")
    ci = observed.get("facts", {}).get("ci")
    if isinstance(ci, dict):
        state = _ci_state(ci, data["candidate"])["state"]
        if state != "success":
            blockers.append(f"ci_{state}")
    else:
        blockers.append("ci_unobserved")
    gate_status = data["gate"]["status"]
    if gate_status not in {"passed", "not_applicable"}:
        blockers.append(f"gate_{gate_status}")
    missing = planner_result.get("missing_confirmation", [])
    if isinstance(missing, list):
        blockers.extend(f"planner_{item}" for item in missing if isinstance(item, str))
    if planner_result.get("action") == "acquire_missing_input_or_handoff":
        blockers.append("planner_requires_input_or_judgment")
    return list(dict.fromkeys(blockers))


def _ci_state(ci: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not ci:
        return {"state": "unobserved", "observed_head_sha": None}
    declared = ci.get("status", "unknown")
    if declared in {"success", "failure"} or (
        declared == "pending"
        and any(
            ci.get(key) is not None
            for key in ("head_sha", "applicable_to")
        )
    ):
        observed_head = ci.get("head_sha")
        applicable = ci.get("applicable_to")
        applicable_head = applicable.get("head_sha") if isinstance(applicable, Mapping) else None
        applicable_base = applicable.get("base_sha") if isinstance(applicable, Mapping) else None
        applicable_effective_base = (
            applicable.get("effective_base_sha") if isinstance(applicable, Mapping) else None
        )
        applicable_members_digest = (
            applicable.get("candidate_members_digest")
            if isinstance(applicable, Mapping)
            else None
        )
        members = candidate.get("members")
        member_digest_required = isinstance(members, list) and len(members) > 1
        expected_members_digest = (
            candidate_member_binding_digest(candidate) if member_digest_required else None
        )
        if (
            observed_head != candidate["head_sha"]
            or applicable_head != candidate["head_sha"]
            or applicable_base != candidate["base_sha"]
            or applicable_effective_base != candidate["effective_base_sha"]
            or (
                member_digest_required
                and applicable_members_digest != expected_members_digest
            )
            or (
                applicable_members_digest is not None
                and not member_digest_required
                and applicable_members_digest != candidate_member_binding_digest(candidate)
            )
        ):
            return {
                "state": "stale",
                "observed_head_sha": observed_head,
                "applicable_head_sha": applicable_head,
                "applicable_base_sha": applicable_base,
                "applicable_effective_base_sha": applicable_effective_base,
                "applicable_candidate_members_digest": applicable_members_digest,
            }
    return {"state": declared, "observed_head_sha": ci.get("head_sha")}


def _review_is_applicable(
    review: Mapping[str, Any], candidate: Mapping[str, Any]
) -> bool:
    applicable = review.get("applicable_to")
    if not isinstance(applicable, Mapping):
        applicable = review
    expected = {
        "candidate_head_sha": candidate["head_sha"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
    }
    if not all(applicable.get(field) == value for field, value in expected.items()):
        return False
    members = candidate.get("members")
    if isinstance(members, list) and len(members) > 1:
        return (
            applicable.get("candidate_members_digest")
            == candidate_member_binding_digest(candidate)
        )
    if "candidate_members_digest" in applicable:
        return applicable.get("candidate_members_digest") == candidate_member_binding_digest(
            candidate
        )
    return True


def _review_state(data: Mapping[str, Any]) -> str:
    facts = data["observed"].get("facts", {})
    review = facts.get("review")
    planner = data["planner"]["result"]
    if isinstance(review, Mapping):
        status = str(review.get("status", "unknown"))
        revision_bound_status = {"evidence_present", "requested", "pending"}
        if status not in revision_bound_status or _review_is_applicable(
            review, data["candidate"]
        ):
            return status
        if planner.get("action") in {
            "request_independent_delta_review",
            "request_related_stack_review",
        }:
            return (
                "requested"
                if planner.get("request_state") != "not_requested"
                else "not_requested"
            )
        return "incomplete"
    if planner.get("action") == "reuse_existing_result":
        return "evidence_present"
    if planner.get("action") in {
        "request_independent_delta_review",
        "request_related_stack_review",
    }:
        return "requested" if planner.get("request_state") != "not_requested" else "not_requested"
    return "unobserved"


def _safe_text(value: Any) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("`", "'")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    escaped: list[str] = []
    for line in lines:
        for character in ("*", "_", "[", "]", "<", ">", "|"):
            line = line.replace(character, f"\\{character}")
        escaped.append(line)
    return "<br>".join(escaped)


def _safe_url(value: Any) -> str:
    url = _require_string(value, "url")
    if not (url.startswith("https://") or url.startswith("http://")):
        return f"`{_safe_text(url)}`"
    return f"<{url.replace('>', '%3E')}>"


def _code(value: Any) -> str:
    text = str(value).replace("`", "'").replace("\r\n", "\n").replace("\r", "\n")
    return f"`{text.replace(chr(10), '<br>')}`"


def _compact_work_value(value: Any) -> str:
    if isinstance(value, (Mapping, list)):
        return canonical_json(value)
    return str(value)


def _diagnostic_checkpoint_lines(work: Mapping[str, Any]) -> list[str]:
    labels = (
        ("failure_scope", "Failure scope"),
        ("current_failure_scope", "Current failure scope"),
        ("evidence_gap", "Evidence gap"),
        ("attempted_paths", "Attempted paths"),
        ("invalidated_paths", "Invalidated paths"),
        ("retry_conditions", "Retry conditions"),
        ("current_hypothesis", "Current hypothesis"),
        ("current_strategy", "Current strategy"),
        ("strategy_attempt_count", "Strategy attempt count"),
        ("exhausted_strategies", "Exhausted strategies"),
        ("strategy_switch_reason", "Strategy switch reason"),
        ("diagnostic_budget", "Diagnostic budget"),
        ("progress_frontier", "Progress frontier"),
        ("last_material_progress", "Last material progress"),
        ("external_wait", "External wait"),
        ("diagnostic_state", "Diagnostic state"),
    )
    return [
        f"- {label}: {_safe_text(_compact_work_value(work[field]))}"
        for field, label in labels
        if field in work
    ]


def _closure_checkpoint_lines(work: Mapping[str, Any]) -> list[str]:
    audit = work.get("closure_audit")
    if not isinstance(audit, list):
        return []
    lines: list[str] = []
    for item in audit:
        if not isinstance(item, Mapping):
            continue
        evidence = ", ".join(str(value) for value in item.get("evidence", []))
        line = (
            f"- {_safe_text(item.get('family', 'unknown'))}: "
            f"{_code(item.get('status', 'unknown'))}"
        )
        if evidence:
            line += f"; evidence: {_safe_text(evidence)}"
        gaps = ", ".join(str(value) for value in item.get("gaps", []))
        if gaps:
            line += f"; gaps: {_safe_text(gaps)}"
        lines.append(line)
    return lines


def _role_lines(data: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for binding in data["revision_bindings"]:
        role = _safe_text(binding["role"])
        label = _safe_text(binding["label"])
        status = _safe_text(binding["status"])
        if binding["status"] == "bound":
            value = _code(binding["revision"])
            source = binding["source"]
            locator = _safe_text(source["locator"])
            lines.append(f"- {label} ({role}): {value}; source: {locator}; status: {status}")
        else:
            reason = _safe_text(binding.get("reason", "not established"))
            lines.append(f"- {label} ({role}): {status}; {reason}")
    if not lines:
        lines.append("- No dependency revision roles were supplied.")
    return lines


def idempotency_key(normalized: NormalizedReviewArtifacts, request_type: str) -> str:
    """Return a stable request identity independent of PR-body observations."""

    _require_string(request_type, "request_type")
    candidate = normalized.data["candidate"]
    planner = normalized.planner_result
    material = {
        "repository": normalized.data["repository"],
        "pull_request_id": candidate["pull_request"]["id"],
        "pull_request_number": candidate["pull_request"]["number"],
        "candidate_head_sha": candidate["head_sha"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "revision_bindings": normalized.data["revision_bindings"],
        "planner_request_key": planner.get("request_key"),
        "planner_scope": planner.get("selected_scope"),
        "review_contract": normalized.data["contract"],
        "request_type": request_type,
    }
    return semantic_digest(material)


def render_review_request(normalized: NormalizedReviewArtifacts) -> str:
    data = normalized.data
    candidate = data["candidate"]
    pr = candidate["pull_request"]
    planner = normalized.planner_result
    action = planner.get("action", "unknown")
    scope = planner.get("selected_scope", {})
    request_identity = idempotency_key(normalized, "review-request")
    lines = [
        f"<!-- {REVIEW_REQUEST_MARKER}:key={request_identity} -->",
        "# Bound review request",
        "",
        f"Candidate: {data['repository']} PR {pr['number']} at {_code(candidate['head_sha'])}",
        "Authority/branch: "
        f"{_safe_text(candidate['authority'])} / {_safe_text(candidate['branch'])}",
        "Base: "
        f"{_code(candidate['base_sha'])}; effective base: "
        f"{_code(candidate['effective_base_sha'])}",
        f"Planner action: {_code(action)}",
    ]
    if isinstance(scope, Mapping):
        lines.append(
            "Planner scope: "
            + _code(scope.get("kind", "unknown"))
            + "; members: "
            + _safe_text(", ".join(str(item) for item in scope.get("members", [])))
        )
        lines.append(
            "Invariants: "
            + _safe_text(", ".join(str(item) for item in scope.get("invariants", [])))
        )
    lines.extend(
        [
            "",
            "## Bound evidence",
            "- CI state: "
            f"{_code(_ci_state(data['observed']['facts'].get('ci', {}), candidate)['state'])}",
            f"- Review evidence state: {_code(_review_state(data))}",
            "- Existing gate result: "
            f"{_code(data['gate']['status'])} (not reinterpreted by this renderer)",
            f"- Render identity: {_code(review_projection_digest(normalized))}",
            "",
            "## Revision roles",
            *_role_lines(data),
        ]
    )
    planner_blockers = [
        reason
        for reason in normalized.blockers
        if reason.startswith("planner_") or reason.startswith("observation_")
    ]
    if action == "acquire_missing_input_or_handoff" or planner_blockers:
        lines.extend(["", "## Not ready for a new request"])
        lines.append(
            "The existing planner or bound evidence requires reconciliation before publication:"
        )
        for blocker in planner_blockers or normalized.blockers:
            lines.append(f"- {_code(blocker)}")
        lines.append("A clean sentence or empty finding list is not approval or resolution.")
    elif action == "reuse_existing_result":
        lines.extend(
            [
                "",
                "The existing planner found applicable review evidence. Reuse its "
                "locator; do not post a duplicate request.",
            ]
        )
        for locator in planner.get("reusable_evidence", []):
            lines.append(f"- Existing evidence: {_safe_text(locator)}")
    elif action == "reconcile_existing_request":
        lines.extend(
            [
                "",
                "An equivalent request is already active or has an unknown submission "
                "result. Reconcile it before retrying.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Please review the selected scope against the candidate and bound "
                "evidence. This request is not acceptance or merge authorization.",
                f"Request identity: {_code(request_identity)}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_pr_description_region(normalized: NormalizedReviewArtifacts) -> str:
    data = normalized.data
    candidate = data["candidate"]
    facts = data["observed"]["facts"]
    ci = _ci_state(facts.get("ci", {}), candidate)
    planner = normalized.planner_result
    lines = [
        GENERATED_REGION_START,
        "### Generated review artifacts",
        "- Candidate: "
        f"{data['repository']} PR {candidate['pull_request']['number']} at "
        f"{_code(candidate['head_sha'])}",
        f"- Effective base: {_code(candidate['effective_base_sha'])}",
        f"- Planner: {_code(planner.get('action', 'unknown'))}",
        f"- CI: {_code(ci['state'])}",
        f"- Review evidence: {_code(_review_state(data))}",
        "- Existing gate result: "
        f"{_code(data['gate']['status'])}; merge authorization remains "
        f"{_code('not established')}",
        f"- Render identity: {_code(review_projection_digest(normalized))}",
        "",
        "#### Revision roles",
        *_role_lines(data),
    ]
    if normalized.blockers:
        lines.extend(["", "#### Current blockers"])
        lines.extend(f"- {_code(blocker)}" for blocker in normalized.blockers)
    else:
        lines.extend(["", "- No renderer-level binding blockers were observed."])
    lines.extend(
        [
            "",
            "This section is a projection of the bound input; human-authored text "
            "outside these markers is preserved.",
            GENERATED_REGION_END,
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def replace_generated_region(
    body: str,
    region: str,
    *,
    initialize: bool = False,
) -> str:
    """Replace exactly one owned region, or explicitly append an initial one."""

    if not isinstance(body, str) or not isinstance(region, str):
        raise RegionOwnershipError("PR body and generated region must be strings")
    start_count = body.count(GENERATED_REGION_START)
    end_count = body.count(GENERATED_REGION_END)
    if start_count == 0 and end_count == 0:
        if not initialize:
            raise RegionOwnershipError("generated PR-description region is missing")
        separator = "" if not body or body.endswith("\n") else "\n"
        return body + separator + "\n" + region.strip("\n") + "\n"
    if start_count != 1 or end_count != 1:
        raise RegionOwnershipError("generated PR-description markers are duplicated or malformed")
    if region.count(GENERATED_REGION_START) != 1 or region.count(GENERATED_REGION_END) != 1:
        raise RegionOwnershipError("replacement region markers are duplicated or malformed")
    region_start = region.index(GENERATED_REGION_START)
    region_end = region.index(GENERATED_REGION_END)
    if region_end < region_start:
        raise RegionOwnershipError("replacement region markers are reversed")
    start = body.index(GENERATED_REGION_START)
    end = body.index(GENERATED_REGION_END)
    if end < start:
        raise RegionOwnershipError("generated PR-description markers are reversed")
    return body[:start] + region.strip("\n") + body[end + len(GENERATED_REGION_END) :]


def render_work_checkpoint(normalized: NormalizedReviewArtifacts) -> str:
    data = normalized.data
    candidate = data["candidate"]
    work = data["work"]
    planner = normalized.planner_result
    checkpoint_identity = idempotency_key(normalized, "work-ledger-checkpoint")
    pr = candidate["pull_request"]
    diagnostic_lines = _diagnostic_checkpoint_lines(work)
    closure_lines = _closure_checkpoint_lines(work)
    lines = [
        f"<!-- {WORK_CHECKPOINT_MARKER}:key={checkpoint_identity} -->",
        "## Work ledger checkpoint",
        "",
        f"- Objective: {_safe_text(work['objective_ref'])}",
        f"- Candidate: {data['repository']} PR {pr['number']} / {_safe_text(candidate['branch'])}",
        f"- Candidate head: {_code(candidate['head_sha'])}",
        "- Base: "
        f"{_code(candidate['base_sha'])}; effective base: "
        f"{_code(candidate['effective_base_sha'])}",
        f"- Planner action: {_code(planner.get('action', 'unknown'))}",
        f"- Gate result: {_code(data['gate']['status'])} (operational projection only)",
        "",
        "### Revision bindings",
        *_role_lines(data),
        "",
        "### Evidence applicability",
        f"- Planner input: {_code(normalized.semantic_digest)}",
        f"- Binding identity: {_code(normalized.binding_digest)}",
        "- CI state: "
        f"{_code(_ci_state(data['observed']['facts'].get('ci', {}), candidate)['state'])}",
        f"- Review evidence state: {_code(_review_state(data))}",
    ]
    if diagnostic_lines:
        lines.extend(["", "### Diagnostic resume state", *diagnostic_lines])
    if closure_lines:
        lines.extend(["", "### Invariant closure audit", *closure_lines])
    lines.extend(["", "### Blockers"])
    blockers = list(work.get("blockers", [])) + list(normalized.blockers)
    if blockers:
        lines.extend(f"- {_code(item)}" for item in sorted(set(blockers)))
    else:
        lines.append("- None recorded by the renderer.")
    lines.extend(
        [
            "",
            "### Referenced findings",
        ]
    )
    refs = work.get("unresolved_finding_refs", [])
    if refs:
        lines.extend(f"- {_safe_text(item)}" for item in refs)
    else:
        lines.append("- None supplied; this checkpoint does not infer resolution.")
    lines.extend(
        [
            "",
            f"- Next safe action: {_safe_text(work['next_safe_action'])}",
            f"- Stopping boundary: {_safe_text(work['stopping_boundary'])}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


class RenderedArtifacts:
    """Pure renderer output keyed by a stable filename."""

    __slots__ = ("files", "manifest", "normalized")

    def __init__(
        self,
        files: dict[str, str],
        manifest: dict[str, Any],
        normalized: NormalizedReviewArtifacts,
    ) -> None:
        self.files = files
        self.manifest = manifest
        self.normalized = normalized

    def write(self, output_dir: str | Path) -> None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in self.files.items():
            (directory / name).write_text(content, encoding="utf-8")


def render(normalized: NormalizedReviewArtifacts) -> RenderedArtifacts:
    """Render every projection from the same normalized source."""

    packet = normalized.as_dict()
    packet["semantic_digest"] = normalized.semantic_digest
    packet["binding_digest"] = normalized.binding_digest
    packet_text = json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    request_text = render_review_request(normalized)
    region_text = render_pr_description_region(normalized)
    checkpoint_text = render_work_checkpoint(normalized)
    files = {
        "review-packet.json": packet_text,
        "review-request.md": request_text,
        "pr-generated-region.md": region_text,
        "work-ledger-checkpoint.md": checkpoint_text,
    }
    file_digests = {name: semantic_digest(content) for name, content in sorted(files.items())}
    manifest = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "kind": INPUT_KIND,
        "semantic_digest": normalized.semantic_digest,
        "binding_digest": normalized.binding_digest,
        "files": file_digests,
        "blockers": list(normalized.blockers),
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return RenderedArtifacts(files, manifest, normalized)


def normalize_and_render(
    source: Mapping[str, Any], *, trusted_base_sha: str
) -> RenderedArtifacts:
    return render(normalize(source, trusted_base_sha=trusted_base_sha))


def _load_input(path: str) -> dict[str, Any]:
    payload = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ArtifactInputError(f"invalid JSON input: {exc}") from exc
    return _require_object(value, "input")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    render_parser = subparsers.add_parser("render", help="validate and render local artifacts")
    render_parser.add_argument(
        "--input", default="-", help="structured JSON input, or '-' for stdin"
    )
    render_parser.add_argument(
        "--trusted-base-sha",
        required=True,
        help="immutable trusted base SHA used to load the maintainer source closure",
    )
    render_parser.add_argument("--output-dir", required=True, help="local output directory")
    args = parser.parse_args(argv)
    try:
        artifacts = normalize_and_render(
            _load_input(args.input), trusted_base_sha=args.trusted_base_sha
        )
        artifacts.write(args.output_dir)
    except (ArtifactInputError, OSError) as exc:
        print(f"ERROR REVIEW_ARTIFACTS: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(artifacts.manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
