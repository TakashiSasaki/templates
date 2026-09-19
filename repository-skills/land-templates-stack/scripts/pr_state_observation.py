#!/usr/bin/env python3
"""Provider-neutral PR observation snapshots and deterministic diffs.

This module deliberately knows nothing about GitHub, review approval, merge
authorization, or finding validity. A provider adapter supplies normalized
records and binding observations; this module only validates, persists in a
stable shape, and compares them.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1
SNAPSHOT_KIND = "pr-state-observation"
FULL_SHA = re.compile(r"[0-9a-f]{40}")

SURFACES = (
    "metadata",
    "checks",
    "reviews",
    "comments",
    "threads",
    "reactions",
)

MODEL_SUMMARY_MAX_BYTES = 8192
SUMMARY_STRING_MAX_CHARS = 512
SUMMARY_PROTECTED_FIELDS = frozenset(
    {
        "identity",
        "id",
        "node_id",
        "database_id",
        "commit_id",
        "head_sha",
        "observed_head_sha",
        "repository_id",
        "resource_id",
    }
)

# These fields describe how a record was observed, not what the provider says
# about the record. In particular, updated_at remains semantic because it can
# identify an edit; retrieved_at and pagination details cannot.
OBSERVATION_ONLY_FIELDS = frozenset(
    {
        "observed_at",
        "retrieved_at",
        "page_index",
        "page_number",
        "cursor",
        "next_cursor",
        "_observation",
    }
)


class ObservationInputError(ValueError):
    """Raised when an observation packet cannot be safely interpreted."""


def _provider_identifier(value: Any, name: str) -> str:
    if type(value) is int and value > 0:
        return str(value)
    return _require_string(value, name)


@dataclass(frozen=True)
class ProviderIdentity:
    """Opaque provider-owned identities for a repository and PR resource."""

    provider: str
    repository_id: str
    resource_id: str

    @classmethod
    def from_mapping(cls, value: Any, name: str) -> ProviderIdentity:
        if not isinstance(value, Mapping):
            raise ObservationInputError(f"{name} must be an object")
        return cls(
            _require_string(value.get("provider"), f"{name}.provider"),
            _provider_identifier(value.get("repository_id"), f"{name}.repository_id"),
            _provider_identifier(value.get("resource_id"), f"{name}.resource_id"),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "repository_id": self.repository_id,
            "resource_id": self.resource_id,
        }


@dataclass(frozen=True)
class DependencyBinding:
    """A declared dependency identity; no dependency head is inferred."""

    identifier: str
    authority: str
    expected_head_sha: str
    provider_identity: ProviderIdentity

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], name: str) -> DependencyBinding:
        identifier = _require_string(value.get("id"), f"{name}.id")
        authority = _require_string(value.get("authority"), f"{name}.authority")
        expected_head_sha = _require_sha(
            value.get("expected_head_sha"), f"{name}.expected_head_sha"
        )
        provider_identity = ProviderIdentity.from_mapping(
            value.get("provider_identity"), f"{name}.provider_identity"
        )
        return cls(identifier, authority, expected_head_sha, provider_identity)

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.identifier,
            "authority": self.authority,
            "expected_head_sha": self.expected_head_sha,
            "provider_identity": self.provider_identity.as_dict(),
        }


@dataclass(frozen=True)
class CandidateBinding:
    """The input identity to which every observed surface must bind."""

    repository: str
    number: int
    identifier: str
    provider_identity: ProviderIdentity
    expected_head_sha: str
    expected_base_sha: str
    dependencies: tuple[DependencyBinding, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CandidateBinding:
        repository = _require_string(value.get("repository"), "candidate.repository")
        number = value.get("number")
        if type(number) is not int or number <= 0:
            raise ObservationInputError("candidate.number must be a positive integer")
        identifier = _require_string(value.get("id"), "candidate.id")
        provider_identity = ProviderIdentity.from_mapping(
            value.get("provider_identity"), "candidate.provider_identity"
        )
        expected_head_sha = _require_sha(
            value.get("expected_head_sha"), "candidate.expected_head_sha"
        )
        expected_base_sha = _require_sha(
            value.get("expected_base_sha"), "candidate.expected_base_sha"
        )
        raw_dependencies = value.get("dependencies", [])
        if not isinstance(raw_dependencies, list):
            raise ObservationInputError("candidate.dependencies must be a list")
        dependencies = tuple(
            DependencyBinding.from_mapping(item, f"candidate.dependencies[{index}]")
            for index, item in enumerate(raw_dependencies)
            if isinstance(item, Mapping)
        )
        if len(dependencies) != len(raw_dependencies):
            raise ObservationInputError("candidate.dependencies entries must be objects")
        identifiers = [item.identifier for item in dependencies]
        if len(identifiers) != len(set(identifiers)):
            raise ObservationInputError("candidate dependency IDs must be unique")
        return cls(
            repository,
            number,
            identifier,
            provider_identity,
            expected_head_sha,
            expected_base_sha,
            dependencies,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "number": self.number,
            "id": self.identifier,
            "provider_identity": self.provider_identity.as_dict(),
            "expected_head_sha": self.expected_head_sha,
            "expected_base_sha": self.expected_base_sha,
            "dependencies": [item.as_dict() for item in self.dependencies],
        }


@dataclass(frozen=True)
class SurfaceObservation:
    """Normalized records and acquisition evidence for one observation surface."""

    complete: bool
    records: tuple[dict[str, Any], ...]
    pages: tuple[dict[str, Any], ...] = ()
    error: dict[str, Any] | None = None
    next_cursor: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], surface: str) -> SurfaceObservation:
        complete = value.get("complete")
        if type(complete) is not bool:
            raise ObservationInputError(f"surfaces.{surface}.complete must be a boolean")
        raw_records = value.get("records", [])
        if not isinstance(raw_records, list):
            raise ObservationInputError(f"surfaces.{surface}.records must be a list")
        records: list[dict[str, Any]] = []
        for index, record in enumerate(raw_records):
            if not isinstance(record, Mapping):
                raise ObservationInputError(
                    f"surfaces.{surface}.records[{index}] must be an object"
                )
            normalized = _json_data(dict(record), f"surfaces.{surface}.records[{index}]")
            identity = record_identity(normalized, f"surfaces.{surface}.records[{index}]")
            normalized["identity"] = identity
            records.append(normalized)
        pages = value.get("pages", [])
        if not isinstance(pages, list) or any(not isinstance(page, Mapping) for page in pages):
            raise ObservationInputError(f"surfaces.{surface}.pages must be a list of objects")
        error = value.get("error")
        if error is not None and not isinstance(error, Mapping):
            raise ObservationInputError(f"surfaces.{surface}.error must be an object or null")
        next_cursor = value.get("next_cursor")
        if next_cursor is not None:
            next_cursor = _require_string(next_cursor, f"surfaces.{surface}.next_cursor")
        return cls(
            complete,
            tuple(sorted(records, key=lambda item: item["identity"])),
            tuple(_json_data(dict(page), f"surfaces.{surface}.pages") for page in pages),
            None if error is None else _json_data(dict(error), f"surfaces.{surface}.error"),
            next_cursor,
        )

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "complete": self.complete,
            "records": [dict(record) for record in self.records],
            "pages": [dict(page) for page in self.pages],
            "error": None if self.error is None else dict(self.error),
        }
        if self.next_cursor is not None:
            result["next_cursor"] = self.next_cursor
        return result


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationInputError(f"{name} must be a non-empty string")
    return value


def _require_sha(value: Any, name: str) -> str:
    result = _require_string(value, name)
    if FULL_SHA.fullmatch(result) is None:
        raise ObservationInputError(f"{name} must be a lowercase full SHA")
    return result


def _json_data(value: Any, name: str) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ObservationInputError(f"{name} contains a non-finite number")
        return value
    if isinstance(value, list):
        return [_json_data(item, f"{name}[]") for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ObservationInputError(f"{name} contains a non-string object key")
        return {key: _json_data(item, f"{name}.{key}") for key, item in value.items()}
    raise ObservationInputError(f"{name} must contain JSON data")


def canonical_json(value: Any) -> str:
    """Serialize JSON data without order-dependent or whitespace differences."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def record_identity(record: Mapping[str, Any], name: str = "record") -> str:
    """Require a provider identity; never synthesize one from a display name."""

    for field in ("identity", "id", "node_id", "database_id", "url"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value
        if field == "id" and type(value) is int and value > 0:
            return str(value)
    raise ObservationInputError(f"{name} has no stable provider identity")


def _binding_observation(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationInputError(f"{name} must be an object")
    provider_identity = ProviderIdentity.from_mapping(
        value.get("provider_identity"), f"{name}.provider_identity"
    )
    head_sha = _require_sha(value.get("head_sha"), f"{name}.head_sha")
    base_sha = _require_sha(value.get("base_sha"), f"{name}.base_sha")
    dependencies = value.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ObservationInputError(f"{name}.dependencies must be a list")
    normalized: list[dict[str, Any]] = []
    for index, dependency in enumerate(dependencies):
        if not isinstance(dependency, Mapping):
            raise ObservationInputError(f"{name}.dependencies[{index}] must be an object")
        identifier = _require_string(dependency.get("id"), f"{name}.dependencies[{index}].id")
        observed_head_sha = _require_sha(
            dependency.get("head_sha"), f"{name}.dependencies[{index}].head_sha"
        )
        dependency_identity = ProviderIdentity.from_mapping(
            dependency.get("provider_identity"),
            f"{name}.dependencies[{index}].provider_identity",
        )
        normalized.append(
            {
                "id": identifier,
                "head_sha": observed_head_sha,
                "provider_identity": dependency_identity.as_dict(),
            }
        )
    if len({item["id"] for item in normalized}) != len(normalized):
        raise ObservationInputError(f"{name}.dependencies must have unique IDs")
    return {
        "provider_identity": provider_identity.as_dict(),
        "head_sha": head_sha,
        "base_sha": base_sha,
        "dependencies": sorted(normalized, key=lambda item: item["id"]),
    }


def binding_mismatch_reasons(
    candidate: CandidateBinding,
    start: Mapping[str, Any],
    end: Mapping[str, Any],
) -> list[str]:
    """Return every binding mismatch; an empty list means stable and expected."""

    normalized_start = _binding_observation(start, "observed_start")
    normalized_end = _binding_observation(end, "observed_end")
    reasons: list[str] = []
    if normalized_start != normalized_end:
        reasons.append("candidate_changed_during_observation")
        if normalized_start["provider_identity"] != normalized_end["provider_identity"]:
            reasons.append("candidate_provider_identity_changed_during_observation")
    for label, observation in (("start", normalized_start), ("end", normalized_end)):
        if observation["head_sha"] != candidate.expected_head_sha:
            reasons.append(f"{label}_head_does_not_match_expected_head")
        if observation["base_sha"] != candidate.expected_base_sha:
            reasons.append(f"{label}_base_does_not_match_expected_base")
        if observation["provider_identity"] != candidate.provider_identity.as_dict():
            reasons.append(f"{label}_provider_identity_does_not_match_expected")
        expected = {
            item.identifier: (item.expected_head_sha, item.provider_identity.as_dict())
            for item in candidate.dependencies
        }
        observed = {
            item["id"]: (item["head_sha"], item["provider_identity"])
            for item in observation["dependencies"]
        }
        if set(expected) != set(observed):
            reasons.append(f"{label}_dependency_binding_incomplete")
        for identifier, (expected_sha, expected_identity) in expected.items():
            observed_value = observed.get(identifier)
            if observed_value is None or observed_value[0] != expected_sha:
                reasons.append(f"{label}_dependency_changed:{identifier}")
            if observed_value is None or observed_value[1] != expected_identity:
                reasons.append(f"{label}_dependency_provider_identity_mismatch:{identifier}")
        start_dependencies = {
            item["id"]: item["provider_identity"] for item in normalized_start["dependencies"]
        }
        end_dependencies = {
            item["id"]: item["provider_identity"] for item in normalized_end["dependencies"]
        }
        for identifier in sorted(set(start_dependencies) & set(end_dependencies)):
            if start_dependencies[identifier] != end_dependencies[identifier]:
                reasons.append(f"dependency_provider_identity_changed:{identifier}")
    return sorted(set(reasons))


def _semantic_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _semantic_value(value)
        for key, value in record.items()
        if key not in OBSERVATION_ONLY_FIELDS
    }


def _semantic_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _semantic_value(item)
            for key, item in value.items()
            if key not in OBSERVATION_ONLY_FIELDS
        }
    if isinstance(value, list):
        return [_semantic_value(item) for item in value]
    return value


def _surface_map(
    snapshot: Mapping[str, Any], surface: str
) -> dict[str, SurfaceObservation]:
    raw_surfaces = snapshot.get("surfaces")
    if not isinstance(raw_surfaces, Mapping):
        raise ObservationInputError("snapshot.surfaces must be an object")
    raw = raw_surfaces.get(surface)
    if not isinstance(raw, Mapping):
        raise ObservationInputError(f"snapshot.surfaces.{surface} is missing")
    return {surface: SurfaceObservation.from_mapping(raw, surface)}


def build_snapshot(
    *,
    candidate: Mapping[str, Any] | CandidateBinding,
    observed_start: Mapping[str, Any],
    observed_end: Mapping[str, Any],
    surfaces: Mapping[str, Mapping[str, Any] | SurfaceObservation],
    requested_surfaces: Sequence[str],
    observation: Mapping[str, Any],
    resume: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a self-contained snapshot without declaring semantic approval."""

    binding = (
        candidate
        if isinstance(candidate, CandidateBinding)
        else CandidateBinding.from_mapping(candidate)
    )
    requested = list(dict.fromkeys(requested_surfaces))
    if not requested:
        raise ObservationInputError("requested_surfaces must not be empty")
    unknown = sorted(set(requested) - set(SURFACES))
    if unknown:
        raise ObservationInputError(f"unknown requested surfaces: {', '.join(unknown)}")
    observation_data = _json_data(dict(observation), "observation")
    normalized_surfaces: dict[str, dict[str, Any]] = {}
    for surface in requested:
        value = surfaces.get(surface)
        if isinstance(value, SurfaceObservation):
            normalized = value
        elif isinstance(value, Mapping):
            normalized = SurfaceObservation.from_mapping(value, surface)
        else:
            raise ObservationInputError(f"missing observation surface: {surface}")
        normalized_surfaces[surface] = normalized.as_dict()
    start = _binding_observation(observed_start, "observed_start")
    end = _binding_observation(observed_end, "observed_end")
    reasons = binding_mismatch_reasons(binding, start, end)
    complete = not reasons and all(
        normalized_surfaces[surface]["complete"] for surface in requested
    )
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": SNAPSHOT_KIND,
        "candidate": binding.as_dict(),
        "requested_surfaces": requested,
        "observed_start": start,
        "observed_end": end,
        "binding_status": "stable" if not reasons else "stale",
        "binding_reasons": reasons,
        "complete": complete,
        "surfaces": normalized_surfaces,
        "observation": observation_data,
        "resume": None if resume is None else _json_data(dict(resume), "resume"),
        # This field makes the non-approval boundary explicit in every saved
        # artifact and prevents a consumer from treating absence as approval.
        "merge_authorization": "not_established",
        "review_approval": "not_inferred",
    }
    snapshot["snapshot_digest"] = sha256_digest(snapshot)
    return snapshot


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate the minimum integrity needed before a snapshot is compared."""

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ObservationInputError("unsupported observation snapshot schema")
    if snapshot.get("kind") != SNAPSHOT_KIND:
        raise ObservationInputError("unsupported observation snapshot kind")
    candidate = snapshot.get("candidate")
    if not isinstance(candidate, Mapping):
        raise ObservationInputError("snapshot.candidate must be an object")
    CandidateBinding.from_mapping(candidate)
    requested = snapshot.get("requested_surfaces")
    if not isinstance(requested, list) or not requested:
        raise ObservationInputError("snapshot.requested_surfaces must be a non-empty list")
    for surface in requested:
        _surface_map(snapshot, surface)
    _binding_observation(snapshot.get("observed_start", {}), "snapshot.observed_start")
    _binding_observation(snapshot.get("observed_end", {}), "snapshot.observed_end")
    declared_digest = snapshot.get("snapshot_digest")
    if not isinstance(declared_digest, str):
        raise ObservationInputError("snapshot.snapshot_digest is missing")
    without_digest = dict(snapshot)
    without_digest.pop("snapshot_digest", None)
    if sha256_digest(without_digest) != declared_digest:
        raise ObservationInputError("snapshot digest does not match its content")


def _snapshot_candidate(snapshot: Mapping[str, Any]) -> CandidateBinding:
    candidate = snapshot.get("candidate")
    if not isinstance(candidate, Mapping):
        raise ObservationInputError("snapshot.candidate must be an object")
    return CandidateBinding.from_mapping(candidate)


def diff_snapshots(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare snapshots without treating incomplete absence as resolution."""

    validate_snapshot(current)
    if previous is None:
        return {
            "status": "initial",
            "meaningful_change": True,
            "counts": {
                "added": 0,
                "changed": 0,
                "state_changed": 0,
                "removed_observed": 0,
                "not_observed": 0,
            },
            "changes": [],
            "unknowns": ["no_previous_snapshot"],
        }
    validate_snapshot(previous)
    previous_candidate = _snapshot_candidate(previous)
    current_candidate = _snapshot_candidate(current)
    if previous_candidate.as_dict() != current_candidate.as_dict():
        return {
            "status": "stale",
            "meaningful_change": False,
            "counts": {},
            "changes": [],
            "unknowns": ["candidate_binding_changed"],
        }
    if current.get("binding_status") != "stable":
        return {
            "status": "stale",
            "meaningful_change": False,
            "counts": {},
            "changes": [],
            "unknowns": list(current.get("binding_reasons", []))
            or ["current_binding_not_stable"],
        }
    if set(previous["requested_surfaces"]) != set(current["requested_surfaces"]):
        return {
            "status": "incomplete",
            "meaningful_change": False,
            "counts": {
                "added": 0,
                "changed": 0,
                "state_changed": 0,
                "removed_observed": 0,
                "not_observed": 0,
            },
            "changes": [],
            "unknowns": ["requested_surface_set_changed"],
            "previous_requested_surfaces": list(previous["requested_surfaces"]),
            "current_requested_surfaces": list(current["requested_surfaces"]),
        }
    if (
        current.get("complete") is not True
        or previous.get("complete") is not True
        or previous.get("binding_status") != "stable"
    ):
        return _incomplete_diff(current, previous)

    changes: list[dict[str, Any]] = []
    counts = {
        "added": 0,
        "changed": 0,
        "state_changed": 0,
        "removed_observed": 0,
        "not_observed": 0,
    }
    previous_surfaces = previous["surfaces"]
    current_surfaces = current["surfaces"]
    requested = sorted(set(current["requested_surfaces"]))
    for surface in requested:
        before = SurfaceObservation.from_mapping(previous_surfaces[surface], surface)
        after = SurfaceObservation.from_mapping(current_surfaces[surface], surface)
        before_by_id = {record["identity"]: record for record in before.records}
        after_by_id = {record["identity"]: record for record in after.records}
        for identity in sorted(set(after_by_id) - set(before_by_id)):
            counts["added"] += 1
            changes.append(
                {
                    "surface": surface,
                    "kind": "added",
                    "identity": identity,
                    "record": after_by_id[identity],
                }
            )
        for identity in sorted(set(before_by_id) & set(after_by_id)):
            before_semantic = _semantic_record(before_by_id[identity])
            after_semantic = _semantic_record(after_by_id[identity])
            if before_semantic == after_semantic:
                continue
            before_state = before_by_id[identity].get("state")
            after_state = after_by_id[identity].get("state")
            kind = "state_changed" if before_state != after_state else "changed"
            counts[kind] += 1
            changes.append(
                {
                    "surface": surface,
                    "kind": kind,
                    "identity": identity,
                    "before": before_by_id[identity],
                    "after": after_by_id[identity],
                }
            )
        if before.complete and after.complete:
            for identity in sorted(set(before_by_id) - set(after_by_id)):
                counts["removed_observed"] += 1
                changes.append(
                    {
                        "surface": surface,
                        "kind": "removed_observed",
                        "identity": identity,
                        "record": before_by_id[identity],
                        "semantic_resolution": "not_inferred",
                    }
                )
        else:
            missing = sorted(set(before_by_id) - set(after_by_id))
            counts["not_observed"] += len(missing)
            changes.extend(
                {
                    "surface": surface,
                    "kind": "not_observed",
                    "identity": identity,
                    "record": before_by_id[identity],
                    "semantic_resolution": "not_inferred",
                }
                for identity in missing
            )
    changes.sort(key=lambda item: (item["surface"], item["identity"], item["kind"]))
    meaningful = any(
        counts[key] for key in ("added", "changed", "state_changed", "removed_observed")
    )
    return {
        "status": "changed" if meaningful else "unchanged",
        "meaningful_change": meaningful,
        "counts": counts,
        "changes": changes,
        "unknowns": [],
    }


def _incomplete_diff(
    current: Mapping[str, Any], previous: Mapping[str, Any]
) -> dict[str, Any]:
    """Expose observations without claiming semantic additions or resolution."""

    changes: list[dict[str, Any]] = []
    current_surfaces = current["surfaces"]
    previous_surfaces = previous["surfaces"]
    for surface in sorted(set(current["requested_surfaces"])):
        current_state = SurfaceObservation.from_mapping(current_surfaces[surface], surface)
        previous_state = SurfaceObservation.from_mapping(previous_surfaces[surface], surface)
        previous_ids = {record["identity"] for record in previous_state.records}
        current_ids = {record["identity"] for record in current_state.records}
        for record in current_state.records:
            if record["identity"] not in previous_ids:
                changes.append(
                    {
                        "surface": surface,
                        "kind": "newly_observed",
                        "identity": record["identity"],
                        "record": record,
                    }
                )
        for record in previous_state.records:
            if record["identity"] not in current_ids:
                changes.append(
                    {
                        "surface": surface,
                        "kind": "not_observed",
                        "identity": record["identity"],
                        "record": record,
                        "semantic_resolution": "not_inferred",
                    }
                )
    changes.sort(key=lambda item: (item["surface"], item["identity"]))
    unknowns: list[str] = []
    if current.get("complete") is not True:
        unknowns.append("current_snapshot_incomplete")
    if previous.get("complete") is not True:
        unknowns.append("previous_snapshot_incomplete")
    if previous.get("binding_status") != "stable":
        unknowns.append("previous_snapshot_binding_not_stable")
    if not unknowns:
        unknowns.append("incomplete_snapshot_baseline")
    return {
        "status": "incomplete",
        "meaningful_change": False,
        "counts": {
            "added": 0,
            "changed": 0,
            "state_changed": 0,
            "removed_observed": 0,
            "newly_observed": sum(
                1 for change in changes if change["kind"] == "newly_observed"
            ),
            "not_observed": sum(
                1
                for change in changes
                if change["kind"] == "not_observed"
            ),
        },
        "changes": changes,
        "unknowns": unknowns,
    }


SUMMARY_RECORD_FIELDS = frozenset(
    {
        "identity",
        "provider_kind",
        "id",
        "node_id",
        "name",
        "title",
        "body",
        "message",
        "state",
        "status",
        "conclusion",
        "context",
        "head_sha",
        "observed_head_sha",
        "workflow_id",
        "run_id",
        "run_attempt",
        "job_id",
        "app_id",
        "commit_id",
        "path",
        "line",
        "start_line",
        "diff_hunk",
        "url",
        "html_url",
        "author",
        "user",
        "dismissed_by",
        "resolved_by",
        "is_resolved",
        "created_at",
        "updated_at",
        "submitted_at",
        "subject_kind",
        "subject_id",
    }
)


def _truncate_summary_string(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    suffix = f"…[truncated;sha256={digest}]"
    return value[: max(0, limit - len(suffix))] + suffix, True


def _summary_value(
    value: Any,
    *,
    key: str | None = None,
    string_limit: int = SUMMARY_STRING_MAX_CHARS,
) -> tuple[Any, bool]:
    if isinstance(value, str):
        if key in SUMMARY_PROTECTED_FIELDS:
            return value, False
        return _truncate_summary_string(value, string_limit)
    if isinstance(value, list):
        normalized: list[Any] = []
        truncated = False
        for item in value:
            item_value, item_truncated = _summary_value(
                item, string_limit=string_limit
            )
            normalized.append(item_value)
            truncated = truncated or item_truncated
        return normalized, truncated
    if isinstance(value, Mapping):
        normalized_mapping: dict[str, Any] = {}
        truncated = False
        for item_key, item in value.items():
            normalized_item, item_truncated = _summary_value(
                item, key=item_key if isinstance(item_key, str) else None,
                string_limit=string_limit,
            )
            normalized_mapping[item_key] = normalized_item
            truncated = truncated or item_truncated
        return normalized_mapping, truncated
    return value, False


def _summary_record(record: Any, *, string_limit: int) -> Any:
    if not isinstance(record, Mapping):
        normalized, _ = _summary_value(record, string_limit=string_limit)
        return normalized
    result: dict[str, Any] = {}
    truncated = False
    for key, value in record.items():
        if key not in SUMMARY_RECORD_FIELDS:
            continue
        normalized, value_truncated = _summary_value(
            value, key=key, string_limit=string_limit
        )
        result[key] = normalized
        truncated = truncated or value_truncated
    if truncated:
        result["detail_digest"] = sha256_digest(dict(record))
    return result


def _summary_change(change: Any, *, string_limit: int) -> Any:
    if not isinstance(change, Mapping):
        normalized, _ = _summary_value(change, string_limit=string_limit)
        return normalized
    result: dict[str, Any] = {}
    truncated = False
    for key, value in change.items():
        if key in {"record", "before", "after"}:
            continue
        normalized, value_truncated = _summary_value(
            value, key=key, string_limit=string_limit
        )
        result[key] = normalized
        truncated = truncated or value_truncated
    for field in ("record", "before", "after"):
        if field in change:
            result[field] = _summary_record(
                change[field], string_limit=string_limit
            )
            if isinstance(change[field], Mapping):
                truncated = truncated or any(
                    isinstance(item, str) and len(item) > string_limit
                    for item in change[field].values()
                )
    if truncated and "detail_digest" not in result:
        result["detail_digest"] = sha256_digest(dict(change))
    return result


def _summary_bytes(value: Any) -> int:
    return len(canonical_json(value).encode("utf-8"))


def _summary_has_truncation(value: Any) -> bool:
    if isinstance(value, Mapping):
        if "detail_digest" in value:
            return True
        return any(_summary_has_truncation(item) for item in value.values())
    if isinstance(value, list):
        return any(_summary_has_truncation(item) for item in value)
    return isinstance(value, str) and "…[truncated;sha256=" in value


def bound_model_summary(value: Any, *, max_bytes: int = MODEL_SUMMARY_MAX_BYTES) -> Any:
    """Bound arbitrary model-facing JSON without changing persisted evidence."""

    if type(max_bytes) is not int or max_bytes <= 0:
        raise ObservationInputError("summary byte limit must be positive")
    for string_limit in (SUMMARY_STRING_MAX_CHARS, 192, 96):
        bounded, _ = _summary_value(value, string_limit=string_limit)
        if _summary_bytes(bounded) <= max_bytes:
            return bounded
    raise ObservationInputError("model-facing summary exceeds its serialized-size bound")


def summarize_diff(
    diff: Mapping[str, Any],
    *,
    limit: int,
    snapshot_reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a bounded model-facing summary while retaining all detail on disk."""

    if type(limit) is not int or limit <= 0:
        raise ObservationInputError("summary limit must be a positive integer")
    changes = diff.get("changes")
    if not isinstance(changes, list):
        raise ObservationInputError("diff.changes must be a list")
    requested_visible = min(limit, len(changes))
    for string_limit in (SUMMARY_STRING_MAX_CHARS, 192, 96):
        visible_count = requested_visible
        while visible_count >= 0:
            omitted = len(changes) - visible_count
            result: dict[str, Any] = {
                "status": diff.get("status"),
                "meaningful_change": diff.get("meaningful_change"),
                "counts": diff.get("counts", {}),
                "changes": [
                    _summary_change(change, string_limit=string_limit)
                    for change in changes[:visible_count]
                ],
                "unknowns": diff.get("unknowns", []),
                "summary_truncated": omitted > 0,
                "omitted_change_count": omitted,
                "merge_authorization": "not_established",
                "review_approval": "not_inferred",
            }
            if snapshot_reference is not None:
                result["detail_reference"] = _summary_value(
                    dict(snapshot_reference), string_limit=string_limit
                )[0]
            if omitted:
                result["continuation"] = {
                    "offset": visible_count,
                    "limit": limit,
                    "snapshot_reference": None
                    if snapshot_reference is None
                    else _summary_value(
                        dict(snapshot_reference), string_limit=string_limit
                    )[0],
                }
            if _summary_has_truncation(result["changes"]):
                result["summary_truncated"] = True
            if _summary_bytes(result) <= MODEL_SUMMARY_MAX_BYTES:
                return result
            visible_count -= 1
    raise ObservationInputError("model-facing diff summary exceeds its serialized-size bound")
