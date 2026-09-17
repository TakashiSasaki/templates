#!/usr/bin/env python3
"""Reconcile an exact qualified source-lock candidate in a fail-closed mode.

This trusted-controller command is intentionally side-effect free.  It returns
the mutation plan that a separate privileged job may apply; candidate code is
never imported or executed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.adopt_publication_sources import plan
from scripts.resolve_publication_sources import SourceLockError, read_json_object


def _key(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reconcile(
    *,
    mode: str,
    current: Path,
    candidate: Path | None,
    qualification: Path | None,
    authorization: bool,
    kill_switch: bool,
    expected_integration_revision: str | None = None,
    expected_policy_revision: str | None = None,
    expected_controller_revision: str | None = None,
) -> dict[str, Any]:
    if mode not in {"shadow", "adoption-only", "auto-publish"}:
        raise SourceLockError("unsupported automation mode")
    current_value = read_json_object(current)
    if candidate is None:
        return {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "authorization",
            "classification": "NO_CHANGE",
            "reason_codes": ["NO_CANDIDATE"],
            "affected_authorities": [],
            "inputs": {"current_lock_digest": hashlib.sha256(current.read_bytes()).hexdigest()},
            "trusted": {"policy_revision": None, "controller_revision": None},
            "checks": {"required": ["candidate-discovery"], "results": {"candidate-discovery": "passed"}, "not_run": []},
            "evidence_refs": [],
            "allowed_mutations": [],
            "next_action": "wait for an exact candidate event",
            "idempotency_key": _key({"boundary": "provider-to-integration", "current": current_value}),
        }
    if qualification is None:
        raise SourceLockError("a qualification report is required for a candidate")
    report = read_json_object(qualification)
    required_report = {"schema_version", "classification", "inputs", "trusted", "checks", "evidence_refs"}
    if (not required_report <= set(report)
            or type(report.get("schema_version")) is not int
            or report["schema_version"] != 1):
        raise SourceLockError("candidate qualification report is incomplete")
    if not isinstance(report.get("inputs"), dict) or not isinstance(report.get("trusted"), dict):
        raise SourceLockError("candidate qualification identities are malformed")
    if not isinstance(report.get("checks"), dict):
        raise SourceLockError("candidate qualification checks are malformed")
    results = report["checks"].get("results", {})
    required_checks = report["checks"].get("required", [])
    evidence_refs = report.get("evidence_refs")
    if (not isinstance(report.get("classification"), str)
            or report["classification"] not in {"NOT_ELIGIBLE", "AUTO_PROCESSABLE"}
            or not isinstance(required_checks, list)
            or not isinstance(results, dict)
            or not isinstance(evidence_refs, list)
            or any(not isinstance(name, str) for name in required_checks)
            or not required_checks
            or any(results.get(name) != "passed" for name in required_checks)
            or not evidence_refs
            or any(not isinstance(value, str) for value in evidence_refs)):
        return {
            **report,
            "stage": "authorization",
            "classification": "QUALIFICATION_FAILED",
            "reason_codes": ["QUALIFICATION_REPORT_NOT_APPLICABLE"],
            "affected_authorities": ["integration"],
            "allowed_mutations": [],
            "next_action": "stop and obtain a new exact qualification report",
        }
    current_publications = current_value.get("publications")
    candidate_value = read_json_object(candidate)
    candidate_publications = candidate_value.get("publications")
    if not isinstance(current_publications, dict) or not isinstance(candidate_publications, dict):
        raise SourceLockError("publication lock has no provider selections")
    for provider, entry in candidate_publications.items():
        if (not isinstance(entry, dict)
                or report["inputs"].get(f"{provider}_revision") != entry.get("revision")):
            return {
                **report,
                "stage": "authorization",
                "classification": "INVALID_INPUT",
                "reason_codes": ["QUALIFICATION_INPUT_DOES_NOT_MATCH_CANDIDATE_LOCK"],
                "affected_authorities": ["integration"],
                "allowed_mutations": [],
                "next_action": "stop and qualify the exact candidate lock",
            }
    if (expected_integration_revision is not None
            and report["inputs"].get("integration_revision") != expected_integration_revision):
        return {
            **report,
            "stage": "authorization",
            "classification": "SUPERSEDED",
            "reason_codes": ["QUALIFICATION_PRODUCER_REVISION_MISMATCH"],
            "affected_authorities": ["integration"],
            "allowed_mutations": [],
            "next_action": "requalify the current Integration producer revision",
        }
    if (expected_policy_revision is not None
            and report["trusted"].get("policy_revision") != expected_policy_revision):
        return {
            **report,
            "stage": "authorization",
            "classification": "NOT_ELIGIBLE",
            "reason_codes": ["TRUSTED_POLICY_REVISION_MISMATCH"],
            "affected_authorities": ["policy"],
            "allowed_mutations": [],
            "next_action": "use the active reviewed Policy pin as the trust root",
        }
    if (expected_controller_revision is not None
            and report["trusted"].get("controller_revision") != expected_controller_revision):
        return {
            **report,
            "stage": "authorization",
            "classification": "SUPERSEDED",
            "reason_codes": ["TRUSTED_CONTROLLER_REVISION_MISMATCH"],
            "affected_authorities": ["integration"],
            "allowed_mutations": [],
            "next_action": "requalify with the current trusted controller",
        }
    mutation = plan(current, candidate)
    if mutation["classification"] == "NO_CHANGE":
        return {**report, **mutation, "stage": "authorization", "classification": "NO_CHANGE", "next_action": "no side effect"}
    if kill_switch:
        return {**report, **mutation, "stage": "authorization", "classification": "NOT_ELIGIBLE", "reason_codes": ["KILL_SWITCH_ACTIVE"], "allowed_mutations": [], "next_action": "keep the current lock and investigate"}
    if mode == "shadow":
        return {**report, **mutation, "stage": "authorization", "classification": "NOT_ELIGIBLE", "reason_codes": ["SHADOW_MODE"], "allowed_mutations": [], "next_action": "compare the report; activation is required before adoption"}
    if not authorization:
        return {**report, **mutation, "stage": "authorization", "classification": "NOT_ELIGIBLE", "reason_codes": ["AUTHORIZATION_NOT_GRANTED"], "allowed_mutations": [], "next_action": "verify the trusted Policy activation grant"}
    return {
        **report,
        **mutation,
        "stage": "authorization",
        "classification": "AUTO_PROCESSABLE",
        "reason_codes": ["QUALIFICATION_PASSED", "AUTHORIZATION_GRANTED", "EXPECTED_MUTATION_MATCH"],
        "allowed_mutations": mutation["allowed_mutations"],
        "next_action": "create or reconcile the idempotent lock adoption PR",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("shadow", "adoption-only", "auto-publish"), default="shadow")
    parser.add_argument("--current", type=Path, default=Path("publication-sources.json"))
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--authorization", action="store_true")
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--expected-integration-revision")
    parser.add_argument("--expected-policy-revision")
    parser.add_argument("--expected-controller-revision")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = reconcile(
            mode=args.mode,
            current=args.current,
            candidate=args.candidate,
            qualification=args.qualification,
            authorization=args.authorization,
            kill_switch=args.kill_switch,
            expected_integration_revision=args.expected_integration_revision,
            expected_policy_revision=args.expected_policy_revision,
            expected_controller_revision=args.expected_controller_revision,
        )
    except (OSError, SourceLockError, ValueError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["classification"])
    return 0 if report["classification"] in {"NO_CHANGE", "NOT_ELIGIBLE", "AUTO_PROCESSABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
