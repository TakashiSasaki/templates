#!/usr/bin/env python3
"""Read-only GitHub PR observation entrypoint with bounded watch support.

The command writes a complete result/snapshot to an explicit local path and
prints only a bounded summary by default. It never submits reviews, changes
PRs, reruns checks, merges, or changes adoption state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pr_state_observation import (  # noqa: E402
    CandidateBinding,
    ObservationInputError,
    SurfaceObservation,
    build_snapshot,
    diff_snapshots,
    record_identity,
    sha256_digest,
    summarize_diff,
)

REQUEST_SCHEMA_VERSION = 1
RESULT_KIND = "pr-state-observation-result"
DEFAULT_SURFACES = (
    "metadata",
    "checks",
    "reviews",
    "comments",
    "threads",
    "reactions",
)
OUTCOMES = {
    "initialized",
    "changed",
    "unchanged",
    "stale",
    "incomplete",
    "unknown",
    "deadline_reached",
    "cancelled",
    "rate_limited",
    "timed_out",
    "malformed",
}
STATUS_LINE = re.compile(r"HTTP/\S+\s+([0-9]{3})")
RETRY_AFTER_LINE = re.compile(r"(?im)^retry-after:\s*([0-9]+(?:\.[0-9]+)?)\s*$")
RATE_LIMIT_TEXT = re.compile(r"rate.?limit|secondary limit|abuse detection", re.I)


class ProviderFailure(RuntimeError):
    """A provider failure that must not be represented as unchanged."""

    def __init__(
        self,
        category: str,
        message: str,
        *,
        retry_at: float | None = None,
        locator: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retry_at = retry_at
        self.locator = locator

    def as_dict(self) -> dict[str, Any]:
        result = {"category": self.category, "message": str(self)}
        if self.retry_at is not None:
            result["retry_at"] = self.retry_at
        if self.locator is not None:
            result["locator"] = self.locator
        return result


class ObservationCancelled(RuntimeError):
    """Raised by a provider or test clock to stop a bounded observation."""


@dataclass(frozen=True)
class ApiResponse:
    payload: Any
    status_code: int | None = None
    retry_at: float | None = None


def _require_object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationInputError(f"{name} must be an object")
    return value


def _parse_deadline(value: Any) -> float:
    if not isinstance(value, str) or not value.strip():
        raise ObservationInputError("deadline must be an RFC3339 timestamp")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ObservationInputError("deadline must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ObservationInputError("deadline must include a timezone")
    return parsed.timestamp()


@dataclass(frozen=True)
class ObservationRequest:
    candidates: tuple[CandidateBinding, ...]
    surfaces: tuple[str, ...]
    mode: str
    deadline: float | None
    max_attempts: int
    summary_limit: int
    snapshot_path: Path
    previous_snapshot_path: Path | None

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        snapshot_override: Path | None = None,
        previous_override: Path | None = None,
    ) -> ObservationRequest:
        if value.get("schema_version") != REQUEST_SCHEMA_VERSION:
            raise ObservationInputError("unsupported observation request schema")
        repository = value.get("repository")
        if repository != "TakashiSasaki/templates":
            raise ObservationInputError("request.repository is not the templates repository")
        raw_candidates = value.get("candidates")
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ObservationInputError("request.candidates must be a non-empty list")
        candidates = tuple(
            CandidateBinding.from_mapping(_require_object(item, "request.candidates[]"))
            for item in raw_candidates
        )
        if any(candidate.repository != repository for candidate in candidates):
            raise ObservationInputError("all candidates must use the request repository")
        identifiers = [candidate.identifier for candidate in candidates]
        if len(identifiers) != len(set(identifiers)):
            raise ObservationInputError("candidate IDs must be unique")
        raw_surfaces = value.get("surfaces", list(DEFAULT_SURFACES))
        if not isinstance(raw_surfaces, list) or not raw_surfaces:
            raise ObservationInputError("request.surfaces must be a non-empty list")
        surfaces = tuple(dict.fromkeys(raw_surfaces))
        unknown = sorted(set(surfaces) - set(DEFAULT_SURFACES))
        if unknown:
            raise ObservationInputError(f"unknown requested surfaces: {', '.join(unknown)}")
        mode = value.get("mode", "single-shot")
        if mode not in {"single-shot", "watch"}:
            raise ObservationInputError("request.mode must be single-shot or watch")
        max_attempts = value.get("max_attempts")
        if type(max_attempts) is not int or max_attempts <= 0:
            raise ObservationInputError("request.max_attempts must be a positive integer")
        if mode == "single-shot" and max_attempts != 1:
            raise ObservationInputError("single-shot requests must use max_attempts=1")
        deadline_value = value.get("deadline")
        deadline = None if deadline_value is None else _parse_deadline(deadline_value)
        if mode == "watch" and deadline is None:
            raise ObservationInputError("watch requests require a deadline")
        summary_limit = value.get("summary_limit", 20)
        if type(summary_limit) is not int or summary_limit <= 0:
            raise ObservationInputError("request.summary_limit must be positive")
        snapshot_value = snapshot_override or value.get("snapshot_path")
        if not isinstance(snapshot_value, (str, Path)) or not str(snapshot_value).strip():
            raise ObservationInputError("an explicit snapshot_path is required")
        previous_value = previous_override or value.get("previous_snapshot_path")
        return cls(
            candidates=candidates,
            surfaces=surfaces,
            mode=mode,
            deadline=deadline,
            max_attempts=max_attempts,
            summary_limit=summary_limit,
            snapshot_path=Path(snapshot_value),
            previous_snapshot_path=None if previous_value is None else Path(previous_value),
        )


class ReadOnlyProvider(Protocol):
    def read_binding(self, candidate: CandidateBinding) -> Mapping[str, Any]:
        ...

    def read_surface(
        self,
        candidate: CandidateBinding,
        surface: str,
        binding: Mapping[str, Any],
    ) -> Mapping[str, Any] | SurfaceObservation:
        ...


def _parse_http_metadata(text: str) -> tuple[int | None, float | None]:
    statuses = [int(value) for value in STATUS_LINE.findall(text)]
    status = statuses[-1] if statuses else None
    retry_after = RETRY_AFTER_LINE.search(text)
    retry_at = None
    if retry_after is not None:
        retry_at = time.time() + float(retry_after.group(1))
    return status, retry_at


def _decode_json_bodies(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    offset = 0
    while offset < len(text):
        candidates = [
            index
            for index, char in enumerate(text[offset:], start=offset)
            if char in "[{"
        ]
        if not candidates:
            break
        parsed = False
        for index in candidates:
            try:
                value, consumed = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            values.append(value)
            offset = index + consumed
            parsed = True
            break
        if not parsed:
            break
    if not values:
        raise ProviderFailure("malformed", "provider response did not contain JSON")
    return values


def _decode_json_body(text: str) -> Any:
    values = _decode_json_bodies(text)
    return values[0]


def gh_api_json(arguments: Sequence[str], *, timeout: float = 30.0) -> ApiResponse:
    """Execute a read-only gh API query and normalize transport failures."""

    if not arguments:
        raise ObservationInputError("gh API arguments must not be empty")
    if arguments[0] == "graphql":
        if any("mutation" in argument.lower() for argument in arguments):
            raise ObservationInputError("GraphQL mutations are not permitted")
        command = ["gh", "api", "graphql", "--include", *arguments[1:]]
    else:
        if any(argument in {"POST", "PUT", "PATCH", "DELETE"} for argument in arguments):
            raise ObservationInputError("write methods are not permitted")
        command = ["gh", "api", "--method", "GET", "--include", *arguments]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ProviderFailure("unavailable", "gh executable is unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderFailure("timeout", "gh API query timed out") from exc
    status, retry_at = _parse_http_metadata(completed.stdout)
    if completed.returncode != 0 or (status is not None and status >= 400):
        details = (completed.stderr or completed.stdout).strip() or "gh API query failed"
        if status in {401, 403} and not RATE_LIMIT_TEXT.search(details):
            category = "permission"
        elif status == 429 or RATE_LIMIT_TEXT.search(details):
            category = "rate_limit"
        else:
            category = "provider"
        raise ProviderFailure(category, details, retry_at=retry_at)
    values = _decode_json_bodies(completed.stdout)
    payload = values if "--paginate" in arguments else values[0]
    return ApiResponse(payload, status, retry_at)


def _page_values(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    return [payload]


def _records_from_pages(
    pages: Sequence[Any],
    *,
    key: str | None,
    surface: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    page_evidence: list[dict[str, Any]] = []
    for page_index, page in enumerate(pages):
        if key is None:
            raw_records = page if isinstance(page, list) else [page]
        elif isinstance(page, Mapping):
            raw_records = page.get(key, [])
        else:
            raise ProviderFailure("malformed", f"{surface} page is not an object")
        if not isinstance(raw_records, list):
            raise ProviderFailure("malformed", f"{surface}.{key} is not a list")
        page_evidence.append(
            {"page_index": page_index, "item_count": len(raw_records), "complete": True}
        )
        for raw in raw_records:
            if not isinstance(raw, Mapping):
                raise ProviderFailure("malformed", f"{surface} record is not an object")
            records.append(dict(raw))
    return records, page_evidence


def _with_identity(
    record: Mapping[str, Any],
    identity: str,
    *,
    provider_kind: str,
) -> dict[str, Any]:
    normalized = dict(record)
    normalized["identity"] = identity
    normalized["provider_kind"] = provider_kind
    return normalized


class GhReadonlyProvider:
    """Small gh api adapter; semantic decisions remain in the existing gate."""

    def __init__(
        self,
        api: Callable[[Sequence[str]], ApiResponse] = gh_api_json,
    ) -> None:
        self.api = api

    def _rest_pages(self, endpoint: str) -> list[Any]:
        response = self.api(("--paginate", endpoint))
        return _page_values(response.payload)

    def _one_rest(self, endpoint: str) -> Mapping[str, Any]:
        pages = self._rest_pages(endpoint)
        if len(pages) != 1 or not isinstance(pages[0], Mapping):
            raise ProviderFailure("malformed", f"expected one object from {endpoint}")
        return pages[0]

    @staticmethod
    def _metadata_path(candidate: CandidateBinding) -> str:
        return f"/repos/{candidate.repository}/pulls/{candidate.number}"

    def _metadata(self, candidate: CandidateBinding) -> Mapping[str, Any]:
        return self._one_rest(self._metadata_path(candidate))

    def read_binding(self, candidate: CandidateBinding) -> Mapping[str, Any]:
        metadata = self._metadata(candidate)
        head = _require_sha_field(metadata, ("head", "sha"), "pull request head")
        base = _require_sha_field(metadata, ("base", "sha"), "pull request base")
        dependencies: list[dict[str, str]] = []
        for dependency in candidate.dependencies:
            if dependency.provider_path is None:
                raise ProviderFailure(
                    "incomplete",
                    f"dependency {dependency.identifier} has no provider_path",
                )
            dependency_metadata = self._one_rest(dependency.provider_path)
            dependency_head = _require_sha_field(
                dependency_metadata,
                ("head", "sha"),
                f"dependency {dependency.identifier} head",
            )
            dependencies.append({"id": dependency.identifier, "head_sha": dependency_head})
        return {
            "head_sha": head,
            "base_sha": base,
            "dependencies": dependencies,
        }

    def read_surface(
        self,
        candidate: CandidateBinding,
        surface: str,
        binding: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        head_sha = binding.get("head_sha")
        if not isinstance(head_sha, str):
            raise ProviderFailure("malformed", "binding head_sha is missing")
        if surface == "metadata":
            metadata = self._metadata(candidate)
            identity = record_identity(metadata, "metadata")
            return {
                "complete": True,
                "records": [_with_identity(metadata, identity, provider_kind="metadata")],
                "pages": [{"page_index": 0, "item_count": 1, "complete": True}],
                "error": None,
            }
        if surface == "checks":
            return self._checks(candidate, head_sha)
        if surface == "reviews":
            return self._simple_surface(
                candidate,
                surface,
                f"/repos/{candidate.repository}/pulls/{candidate.number}/reviews",
            )
        if surface == "comments":
            return self._simple_surface(
                candidate,
                surface,
                f"/repos/{candidate.repository}/issues/{candidate.number}/comments",
            )
        if surface == "threads":
            return self._threads(candidate)
        if surface == "reactions":
            return self._reactions(candidate)
        raise ObservationInputError(f"unsupported provider surface: {surface}")

    def _simple_surface(
        self,
        candidate: CandidateBinding,
        surface: str,
        endpoint: str,
    ) -> Mapping[str, Any]:
        del candidate
        pages = self._rest_pages(endpoint)
        raw_records, pages_evidence = _records_from_pages(pages, key=None, surface=surface)
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_records:
            identity = record_identity(raw, surface)
            if identity in seen:
                raise ProviderFailure("malformed", f"duplicate {surface} identity {identity}")
            seen.add(identity)
            records.append(_with_identity(raw, identity, provider_kind=surface))
        return {"complete": True, "records": records, "pages": pages_evidence, "error": None}

    def _checks(self, candidate: CandidateBinding, head_sha: str) -> Mapping[str, Any]:
        check_pages = self._rest_pages(
            f"/repos/{candidate.repository}/commits/{head_sha}/check-runs"
        )
        status_pages = self._rest_pages(
            f"/repos/{candidate.repository}/commits/{head_sha}/status"
        )
        check_records, check_evidence = _records_from_pages(
            check_pages, key="check_runs", surface="checks"
        )
        status_records, status_evidence = _records_from_pages(
            status_pages, key="statuses", surface="checks"
        )
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in check_records:
            raw_id = raw.get("id")
            if not isinstance(raw_id, (str, int)):
                raise ProviderFailure("malformed", "check run has no stable id")
            identity = f"check-run:{raw_id}"
            if identity in seen:
                raise ProviderFailure("malformed", f"duplicate check identity {identity}")
            seen.add(identity)
            records.append(
                _with_identity(
                    {**raw, "observed_head_sha": head_sha},
                    identity,
                    provider_kind="check_run",
                )
            )
        for raw in status_records:
            context = raw.get("context")
            target_url = raw.get("target_url") or ""
            if not isinstance(context, str) or not context:
                raise ProviderFailure("malformed", "status context is missing")
            identity = f"status:{head_sha}:{context}:{target_url}"
            if identity in seen:
                raise ProviderFailure("malformed", f"duplicate status identity {identity}")
            seen.add(identity)
            records.append(
                _with_identity(
                    {**raw, "observed_head_sha": head_sha},
                    identity,
                    provider_kind="commit_status",
                )
            )
        return {
            "complete": True,
            "records": records,
            "pages": [*check_evidence, *status_evidence],
            "error": None,
        }

    def _graphql(self, query: str, variables: Mapping[str, Any]) -> Any:
        arguments = ["graphql", "-f", f"query={query}"]
        for name, value in variables.items():
            if value is not None:
                flag = "-F" if isinstance(value, (int, float, bool)) else "-f"
                arguments.extend([flag, f"{name}={value}"])
        response = self.api(arguments)
        payload = response.payload
        if not isinstance(payload, Mapping):
            raise ProviderFailure("malformed", "GraphQL response is not an object")
        if payload.get("errors"):
            raise ProviderFailure("provider", "GraphQL response contains errors")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise ProviderFailure("malformed", "GraphQL data is missing")
        return data

    def _threads(self, candidate: CandidateBinding) -> Mapping[str, Any]:
        query = """
        query($owner:String!,$repo:String!,$number:Int!,$after:String) {
          repository(owner:$owner,name:$repo) {
            pullRequest(number:$number) {
              reviewThreads(first:100,after:$after) {
                nodes {
                  id isResolved resolvedBy { login }
                  comments(first:100) {
                    nodes { id body path line diffHunk createdAt updatedAt url author { login } }
                    pageInfo { hasNextPage endCursor }
                  }
                }
                pageInfo { hasNextPage endCursor }
              }
            }
          }
        }
        """
        owner, repo = candidate.repository.split("/", 1)
        after: str | None = None
        threads: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        while True:
            data = self._graphql(
                query,
                {"owner": owner, "repo": repo, "number": candidate.number, "after": after},
            )
            repository = data.get("repository")
            pull_request = (
                repository.get("pullRequest") if isinstance(repository, Mapping) else None
            )
            connection = (
                pull_request.get("reviewThreads")
                if isinstance(pull_request, Mapping)
                else None
            )
            if not isinstance(connection, Mapping):
                raise ProviderFailure("malformed", "reviewThreads connection is missing")
            nodes = connection.get("nodes", [])
            page_info = connection.get("pageInfo", {})
            if not isinstance(nodes, list) or not isinstance(page_info, Mapping):
                raise ProviderFailure("malformed", "reviewThreads page is malformed")
            pages.append({"page_index": len(pages), "item_count": len(nodes), "complete": True})
            for node in nodes:
                if not isinstance(node, Mapping):
                    raise ProviderFailure("malformed", "review thread is malformed")
                identity = record_identity(node, "review thread")
                thread = dict(node)
                thread["identity"] = identity
                thread["provider_kind"] = "review_thread"
                comments = node.get("comments", {})
                if not isinstance(comments, Mapping):
                    raise ProviderFailure("malformed", "review thread comments are malformed")
                comment_page_info = comments.get("pageInfo", {})
                if isinstance(comment_page_info, Mapping) and comment_page_info.get("hasNextPage"):
                    raise ProviderFailure(
                        "incomplete",
                        f"review thread {identity} comments require another cursor",
                    )
                threads.append(thread)
            if page_info.get("hasNextPage") is not True:
                break
            after = page_info.get("endCursor")
            if not isinstance(after, str) or not after:
                raise ProviderFailure("malformed", "review thread cursor is missing")
        return {"complete": True, "records": threads, "pages": pages, "error": None}

    def _reactions(self, candidate: CandidateBinding) -> Mapping[str, Any]:
        records: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        owner, repo = candidate.repository.split("/", 1)

        reaction_endpoints = [
            (
                f"/repos/{owner}/{repo}/issues/{candidate.number}/reactions",
                "pull_request",
                str(candidate.number),
            )
        ]
        issue_comment_pages = self._rest_pages(
            f"/repos/{candidate.repository}/issues/{candidate.number}/comments"
        )
        issue_comments, issue_pages = _records_from_pages(
            issue_comment_pages, key=None, surface="reactions.issue_comments"
        )
        pages.extend(issue_pages)
        for comment in issue_comments:
            comment_id = comment.get("id")
            if not isinstance(comment_id, (str, int)):
                raise ProviderFailure("malformed", "issue comment has no stable id")
            reaction_endpoints.append(
                (
                    f"/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions",
                    "issue_comment",
                    str(comment_id),
                )
            )

        review_comment_pages = self._rest_pages(
            f"/repos/{candidate.repository}/pulls/{candidate.number}/comments"
        )
        review_comments, review_pages = _records_from_pages(
            review_comment_pages, key=None, surface="reactions.review_comments"
        )
        pages.extend(review_pages)
        for comment in review_comments:
            comment_id = comment.get("id")
            if not isinstance(comment_id, (str, int)):
                raise ProviderFailure("malformed", "review comment has no stable id")
            reaction_endpoints.append(
                (
                    f"/repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions",
                    "review_comment",
                    str(comment_id),
                )
            )

        for endpoint, subject_kind, subject_id in reaction_endpoints:
            reaction_pages = self._rest_pages(endpoint)
            raw_reactions, reaction_evidence = _records_from_pages(
                reaction_pages,
                key=None,
                surface="reactions",
            )
            pages.extend(reaction_evidence)
            for raw in raw_reactions:
                raw_id = raw.get("id")
                if not isinstance(raw_id, (str, int)):
                    raise ProviderFailure("malformed", "reaction has no stable id")
                identity = f"{subject_kind}:{subject_id}:reaction:{raw_id}"
                records.append(
                    _with_identity(
                        {**raw, "subject_kind": subject_kind, "subject_id": subject_id},
                        identity,
                        provider_kind="reaction",
                    )
                )
        return {"complete": True, "records": records, "pages": pages, "error": None}


def _require_sha_field(value: Mapping[str, Any], path: tuple[str, ...], name: str) -> str:
    current: Any = value
    for part in path:
        if not isinstance(current, Mapping):
            raise ProviderFailure("malformed", f"{name} is malformed")
        current = current.get(part)
    if not isinstance(current, str) or re.fullmatch(r"[0-9a-f]{40}", current) is None:
        raise ProviderFailure("malformed", f"{name} is not a full SHA")
    return current


@dataclass(frozen=True)
class Capture:
    snapshot: dict[str, Any] | None
    failure: ProviderFailure | None


def capture_once(
    provider: ReadOnlyProvider,
    candidate: CandidateBinding,
    surfaces: Sequence[str],
    *,
    clock: Callable[[], float],
) -> Capture:
    started_time = clock()
    started_at = dt.datetime.fromtimestamp(started_time, dt.UTC).isoformat()
    try:
        observed_start = dict(provider.read_binding(candidate))
    except ProviderFailure as failure:
        return Capture(None, failure)
    surface_values: dict[str, Mapping[str, Any] | SurfaceObservation] = {}
    failure: ProviderFailure | None = None
    for surface in surfaces:
        try:
            surface_values[surface] = provider.read_surface(
                candidate,
                surface,
                observed_start,
            )
        except ProviderFailure as current_failure:
            failure = current_failure
            surface_values[surface] = {
                "complete": False,
                "records": [],
                "pages": [],
                "error": current_failure.as_dict(),
            }
    try:
        observed_end = dict(provider.read_binding(candidate))
    except ProviderFailure as current_failure:
        return Capture(None, current_failure)
    ended_time = clock()
    try:
        snapshot = build_snapshot(
            candidate=candidate,
            observed_start=observed_start,
            observed_end=observed_end,
            surfaces=surface_values,
            requested_surfaces=surfaces,
            observation={
                "provider": provider.__class__.__name__,
                "started_at": started_at,
                "ended_at": dt.datetime.fromtimestamp(
                    ended_time, dt.UTC
                ).isoformat(),
                "interval_seconds": max(0.0, ended_time - started_time),
            },
        )
    except ObservationInputError as exc:
        return Capture(None, ProviderFailure("malformed", str(exc)))
    return Capture(snapshot, failure)


def _load_bundle(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationInputError(f"cannot load previous snapshot: {path}") from exc
    if not isinstance(data, Mapping):
        raise ObservationInputError("previous snapshot must be an object")
    return dict(data)


def _previous_by_candidate(
    bundle: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if bundle is None:
        return {}
    snapshots = bundle.get("snapshots")
    if isinstance(snapshots, Mapping):
        return {
            str(identifier): snapshot
            for identifier, snapshot in snapshots.items()
            if isinstance(snapshot, Mapping)
        }
    if bundle.get("kind") == "pr-state-observation":
        candidate = bundle.get("candidate")
        if isinstance(candidate, Mapping) and isinstance(candidate.get("id"), str):
            return {candidate["id"]: bundle}
    return {}


def _ensure_external_path(path: Path, repository_root: Path) -> Path:
    expanded = path.expanduser()
    if expanded.exists() and expanded.is_symlink():
        raise ObservationInputError("snapshot path must not be a symlink")
    resolved = expanded.resolve()
    root = repository_root.resolve()
    if resolved == root or resolved.is_relative_to(root):
        raise ObservationInputError("snapshot path must be outside the repository")
    if not resolved.parent.is_dir():
        raise ObservationInputError("snapshot parent directory must exist")
    return resolved


def write_json_atomic(
    path: Path,
    value: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, str]:
    resolved = _ensure_external_path(path, repository_root)
    encoded = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=resolved.parent,
            prefix=f".{resolved.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.chmod(temporary_path, 0o600)
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, resolved)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return {"path": str(resolved), "digest": sha256_digest(value)}


def _failure_outcome(failure: ProviderFailure) -> str:
    return {
        "permission": "unknown",
        "unavailable": "unknown",
        "provider": "unknown",
        "malformed": "malformed",
        "timeout": "timed_out",
        "rate_limit": "rate_limited",
        "incomplete": "incomplete",
    }.get(failure.category, "unknown")


def _backoff_seconds(attempt: int) -> float:
    return min(30.0, float(2 ** max(0, attempt - 1)))


def observe(
    request: ObservationRequest,
    provider: ReadOnlyProvider,
    *,
    repository_root: Path,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run a single-shot or bounded watch and return the full persisted result."""

    previous_bundle = _load_bundle(request.previous_snapshot_path)
    previous = _previous_by_candidate(previous_bundle)
    snapshots: dict[str, dict[str, Any]] = {}
    candidate_results: list[dict[str, Any]] = []
    overall_outcome = "initialized"
    attempt = 0
    last_failure: ProviderFailure | None = None
    while attempt < request.max_attempts:
        attempt += 1
        if request.deadline is not None and clock() >= request.deadline:
            overall_outcome = "deadline_reached"
            break
        candidate_results = []
        snapshots = {}
        should_wait = False
        iteration_outcomes: list[str] = []
        last_failure = None
        for candidate in request.candidates:
            capture = capture_once(provider, candidate, request.surfaces, clock=clock)
            last_failure = capture.failure
            if capture.snapshot is None:
                failure = capture.failure or ProviderFailure("unknown", "capture failed")
                outcome = _failure_outcome(failure)
                iteration_outcomes.append(outcome)
                candidate_results.append(
                    {
                        "candidate_id": candidate.identifier,
                        "outcome": outcome,
                        "error": failure.as_dict(),
                        "merge_authorization": "not_established",
                        "review_approval": "not_inferred",
                    }
                )
                if request.mode == "watch" and outcome in {
                    "rate_limited",
                    "timed_out",
                    "incomplete",
                }:
                    should_wait = True
                else:
                    break
                continue
            current = capture.snapshot
            snapshots[candidate.identifier] = current
            diff = diff_snapshots(previous.get(candidate.identifier), current)
            if current["binding_status"] != "stable":
                outcome = "stale"
            elif previous.get(candidate.identifier) is None:
                outcome = "initialized" if current["complete"] else "incomplete"
            elif diff["status"] == "stale":
                outcome = "stale"
            elif diff["status"] == "incomplete":
                outcome = "incomplete"
            else:
                outcome = diff["status"]
            iteration_outcomes.append(outcome)
            candidate_results.append(
                {
                    "candidate_id": candidate.identifier,
                    "outcome": outcome,
                    "diff": diff,
                    "snapshot_digest": current["snapshot_digest"],
                    "merge_authorization": "not_established",
                    "review_approval": "not_inferred",
                }
            )
            if request.mode == "watch" and outcome in {"initialized", "unchanged"}:
                should_wait = True
            elif outcome not in {"initialized", "unchanged"}:
                should_wait = False
                break
        if "changed" in iteration_outcomes:
            overall_outcome = "changed"
        elif "stale" in iteration_outcomes:
            overall_outcome = "stale"
        elif "incomplete" in iteration_outcomes:
            overall_outcome = "incomplete"
        elif any(
            outcome in {"unknown", "malformed", "timed_out", "rate_limited"}
            for outcome in iteration_outcomes
        ):
            overall_outcome = next(
                outcome
                for outcome in iteration_outcomes
                if outcome in {"unknown", "malformed", "timed_out", "rate_limited"}
            )
        elif iteration_outcomes and all(outcome == "unchanged" for outcome in iteration_outcomes):
            overall_outcome = "unchanged"
        else:
            overall_outcome = "initialized"
        if overall_outcome in {
            "changed",
            "stale",
            "incomplete",
            "unknown",
            "malformed",
            "timed_out",
        }:
            if overall_outcome == "incomplete" and should_wait:
                pass
            else:
                break
        if request.mode == "single-shot":
            break
        if not should_wait:
            break
        previous.update(
            {
                identifier: snapshot
                for identifier, snapshot in snapshots.items()
                if snapshot.get("complete") is True
                and snapshot.get("binding_status") == "stable"
            }
        )
        if attempt >= request.max_attempts:
            overall_outcome = "deadline_reached"
            break
        now = clock()
        if request.deadline is not None and now >= request.deadline:
            overall_outcome = "deadline_reached"
            break
        delay = _backoff_seconds(attempt)
        if last_failure is not None and last_failure.retry_at is not None:
            delay = max(0.0, last_failure.retry_at - now)
        if request.deadline is not None:
            delay = min(delay, max(0.0, request.deadline - now))
        if delay <= 0:
            overall_outcome = "deadline_reached"
            break
        try:
            sleep(delay)
        except (KeyboardInterrupt, ObservationCancelled):
            overall_outcome = "cancelled"
            break
    if attempt >= request.max_attempts and request.mode == "watch" and overall_outcome in {
        "initialized",
        "unchanged",
    }:
        overall_outcome = "deadline_reached"
    if not candidate_results and overall_outcome == "initialized":
        overall_outcome = "unknown"
    termination = {
        "deadline_reached": "deadline",
        "cancelled": "cancelled",
        "rate_limited": "rate_limit",
        "timed_out": "timeout",
        "unknown": "error",
        "malformed": "error",
    }.get(overall_outcome, "completed")
    full_result: dict[str, Any] = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "kind": RESULT_KIND,
        "outcome": overall_outcome,
        "termination": termination,
        "attempts": attempt,
        "candidates": candidate_results,
        "snapshots": snapshots,
        "resume": {
            "previous_snapshot_path": None
            if request.previous_snapshot_path is None
            else str(request.previous_snapshot_path),
            "last_attempt": attempt,
            "reason": overall_outcome,
        },
        "merge_authorization": "not_established",
        "review_approval": "not_inferred",
    }
    full_result["result_digest"] = sha256_digest(full_result)
    reference = write_json_atomic(
        request.snapshot_path,
        full_result,
        repository_root=repository_root,
    )
    full_result["snapshot_reference"] = reference
    return full_result


def bounded_summary(result: Mapping[str, Any], limit: int) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for candidate in result.get("candidates", []):
        item = dict(candidate)
        diff = item.get("diff")
        if isinstance(diff, Mapping):
            item["diff"] = summarize_diff(
                diff,
                limit=limit,
                snapshot_reference=result.get("snapshot_reference"),
            )
        candidates.append(item)
    return {
        "kind": result.get("kind"),
        "outcome": result.get("outcome"),
        "termination": result.get("termination"),
        "attempts": result.get("attempts"),
        "candidates": candidates,
        "snapshot_reference": result.get("snapshot_reference"),
        "resume": result.get("resume"),
        "merge_authorization": "not_established",
        "review_approval": "not_inferred",
    }


def _read_json_input(path: Path | None) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8") if path is not None else sys.stdin.read()
        value = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationInputError("observation request is not valid JSON") from exc
    return _require_object(value, "request")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON request path; stdin when omitted")
    parser.add_argument("--snapshot", type=Path, help="explicit non-Git-tracked result path")
    parser.add_argument("--previous-snapshot", type=Path)
    parser.add_argument("--debug", action="store_true", help="print the full result")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw_request = _read_json_input(args.input)
        request = ObservationRequest.from_mapping(
            raw_request,
            snapshot_override=args.snapshot,
            previous_override=args.previous_snapshot,
        )
        result = observe(
            request,
            GhReadonlyProvider(),
            repository_root=Path.cwd(),
        )
    except ObservationInputError as exc:
        print(
            json.dumps(
                {
                    "kind": RESULT_KIND,
                    "outcome": "malformed",
                    "error": str(exc),
                    "merge_authorization": "not_established",
                },
                ensure_ascii=False,
            )
        )
        return 2
    except ProviderFailure as exc:
        print(
            json.dumps(
                {
                    "kind": RESULT_KIND,
                    "outcome": _failure_outcome(exc),
                    "error": exc.as_dict(),
                    "merge_authorization": "not_established",
                },
                ensure_ascii=False,
            )
        )
        return 1
    output = result if args.debug else bounded_summary(result, request.summary_limit)
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
