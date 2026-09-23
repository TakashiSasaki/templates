#!/usr/bin/env python3
"""Operational live revalidation adapter for templates maintainer workflow.

Composes the existing PR observer, immutable planner source, shared gate result,
and canonical effective-base resolution into a reusable adapter satisfying the
publish_review_artifacts live-adapter contract.
"""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def _load_sibling(name: str, filename: str) -> Any:
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling module {filename} from {SCRIPT_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise
    return module


publisher = _load_sibling("templates_publish_review_artifacts", "publish_review_artifacts.py")
renderer = publisher.renderer

FULL_SHA = re.compile(r"[0-9a-f]{40}")


class AdapterConfigurationError(ValueError):
    """Raised when the operational adapter cannot establish a valid configuration."""


def default_planner_packet_builder(
    normalized: Any, snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the live planner packet from normalized context and live observed snapshot.

    Preserves exact candidate head/base/effective_base and Work-ledger readiness.
    """
    packet = copy.deepcopy(normalized.planner_packet)
    cand = packet.setdefault("candidate", {})
    if isinstance(snapshot, Mapping):
        obs_cand = snapshot.get("candidate", {})
        if isinstance(obs_cand, Mapping):
            if "expected_head_sha" in obs_cand:
                cand["head_sha"] = obs_cand["expected_head_sha"]
            if "expected_base_sha" in obs_cand:
                cand["base_sha"] = obs_cand["expected_base_sha"]
    return packet


def default_effective_base_resolver(
    normalized: Any, payload: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Resolve effective base commit SHA from stack topology or PR base."""
    del snapshot
    head_map = payload.get("head") if isinstance(payload.get("head"), Mapping) else {}
    base_map = payload.get("base") if isinstance(payload.get("base"), Mapping) else {}
    head_sha = head_map.get("sha")
    base_sha = base_map.get("sha")
    if not head_sha or not base_sha:
        raise AdapterConfigurationError("live PR payload missing head or base SHA")

    cand = normalized.data.get("candidate", {})
    cand_effective = cand.get("effective_base_sha")

    members = cand.get("members", [])
    target_pr_number = cand.get("pull_request", {}).get("number")
    effective_sha = None

    if isinstance(members, list) and len(members) > 1 and target_pr_number:
        for idx, member in enumerate(members):
            if not isinstance(member, Mapping):
                continue
            pr_data = member.get("pull_request", {})
            if isinstance(pr_data, Mapping) and pr_data.get("number") == target_pr_number:
                if idx > 0 and isinstance(members[idx - 1], Mapping):
                    effective_sha = members[idx - 1].get("head_sha")
                else:
                    effective_sha = base_sha
                break

    if effective_sha is None:
        effective_sha = cand_effective or base_sha

    if not isinstance(effective_sha, str) or not FULL_SHA.fullmatch(effective_sha):
        raise AdapterConfigurationError(f"invalid effective base SHA: {effective_sha}")

    return {
        "complete": True,
        "source": "canonical_effective_base_resolver",
        "sha": effective_sha,
        "candidate_head_sha": head_sha,
        "base_sha": base_sha,
    }


def default_gate_resolver(
    normalized: Any,
    snapshot: Mapping[str, Any],
    packet: Mapping[str, Any],
    planner_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve gate status and bind to live candidate and planner inputs.

    Never synthesizes fictitious approvals: uses explicit gate input if provided,
    or reports 'pending' / 'not_evaluated' with concrete unverified status.
    """
    del snapshot
    gate_data = normalized.data.get("gate", {})
    gate_status = gate_data.get("status", "not_evaluated")

    head_sha = packet["candidate"]["head_sha"]
    base_sha = packet["candidate"]["base_sha"]
    effective_base_sha = packet["candidate"]["effective_base_sha"]

    input_binding = {
        "repository": normalized.data["repository"],
        "pull_request_id": normalized.data["candidate"]["pull_request"]["id"],
        "candidate_head_sha": head_sha,
        "base_sha": base_sha,
        "effective_base_sha": effective_base_sha,
        "revision_bindings_digest": renderer.semantic_digest(
            normalized.data["revision_bindings"]
        ),
        "planner_input_digest": renderer.semantic_digest(packet),
        "planner_result_digest": renderer.semantic_digest(planner_result),
    }

    input_binding_digest = renderer.semantic_digest(input_binding)

    result = {
        "status": gate_status,
        "input_binding": input_binding,
        "input_binding_digest": input_binding_digest,
    }
    if "evidence_digest" in gate_data:
        result["evidence_digest"] = gate_data["evidence_digest"]
    return result


def create_live_review_adapter(
    normalized: Any,
    *,
    planner_packet_builder: (
        Callable[[Any, Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
    gate_resolver: (
        Callable[[Any, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
        | None
    ) = None,
    effective_base_resolver: (
        Callable[[Any, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]] | None
    ) = None,
    clock: Callable[[], float] = time.time,
    observation_seconds: float = 60.0,
) -> Any:
    """Create a configured GitHubLiveRevalidationAdapter instance."""
    del normalized
    return publisher.GitHubLiveRevalidationAdapter(
        planner_packet_builder=planner_packet_builder or default_planner_packet_builder,
        gate_resolver=gate_resolver or default_gate_resolver,
        effective_base_resolver=effective_base_resolver or default_effective_base_resolver,
        clock=clock,
        observation_seconds=observation_seconds,
    )


def resolve(
    context: Any,
    payload: Mapping[str, Any],
    provider: Any,
) -> Mapping[str, Any]:
    """Standard operational live adapter entrypoint callable by publish_review_artifacts.

    Satisfies the --live-adapter MODULE:FUNCTION or FILE.py:FUNCTION contract.
    """
    adapter = create_live_review_adapter(context)
    return adapter(context, payload, provider)
