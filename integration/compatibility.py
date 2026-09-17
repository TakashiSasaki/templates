"""Fail-closed publication compatibility and qualification classifier.

The classifier deliberately has no GitHub or provider-specific side effects.  A
controller may use its report as a positive gate only after independently
checking the trusted policy and release authorization.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
PROVIDERS = frozenset({"modeling", "composition", "policy"})
CLASSIFICATIONS = frozenset(
    {
        "COMPATIBLE_PENDING_QUALIFICATION", "AUTO_PROCESSABLE", "ADAPTATION_REQUIRED",
        "CROSS_PROVIDER_CONFLICT", "INVALID_INPUT", "UNKNOWN", "QUALIFICATION_FAILED",
        "INFRASTRUCTURE_FAILURE", "NOT_ELIGIBLE", "SUPERSEDED", "NO_CHANGE",
    }
)


class CompatibilityError(ValueError):
    """Base class for typed, structured classifier failures."""


class InvalidInputError(CompatibilityError):
    pass


class UnknownEnvelopeError(CompatibilityError):
    pass


class CrossProviderConflictError(CompatibilityError):
    pass


@dataclass(frozen=True)
class Requirement:
    feature: str
    required: bool
    fallback: str


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not FULL_SHA.fullmatch(value):
        raise InvalidInputError(f"{field} must be a full lowercase commit SHA")
    return value


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX_DIGEST.fullmatch(value):
        raise InvalidInputError(f"{field} must be a SHA-256 digest")
    return value


def _requirements(value: Any) -> list[Requirement]:
    if not isinstance(value, list):
        raise InvalidInputError("requirements must be an array")
    result: list[Requirement] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != {"feature", "required", "fallback"}:
            raise InvalidInputError(f"requirements[{index}] has an invalid shape")
        feature, required, fallback = raw["feature"], raw["required"], raw["fallback"]
        if not isinstance(feature, str) or not feature or feature in seen:
            raise InvalidInputError(f"requirements[{index}].feature is missing or duplicated")
        if type(required) is not bool or fallback not in {"none", "generic-document", "ignore"}:
            raise InvalidInputError(f"requirements[{index}] has an invalid required/fallback value")
        seen.add(feature)
        result.append(Requirement(feature, required, fallback))
    return result


def _trusted(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"policy_revision", "controller_revision"}:
        raise InvalidInputError("trusted must contain policy_revision and controller_revision")
    return {
        "policy_revision": _sha(value["policy_revision"], "trusted.policy_revision"),
        "controller_revision": _sha(value["controller_revision"], "trusted.controller_revision"),
    }


def _inputs(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise InvalidInputError("inputs must be a non-empty identity object")
    result: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key or not isinstance(raw, str):
            raise InvalidInputError("input identities must be string keyed")
        if key.endswith("_revision"):
            result[key] = _sha(raw, f"inputs.{key}")
        elif key.endswith(("_digest", "_identity")):
            result[key] = _digest(raw, f"inputs.{key}")
        else:
            result[key] = raw
    return result


def _base_report(payload: Mapping[str, Any], stage: str) -> dict[str, Any]:
    boundary = payload.get("boundary")
    if boundary not in {"provider-to-integration", "integration-to-site", "site-to-pages"}:
        raise InvalidInputError("unsupported boundary")
    if stage not in {"preflight", "qualification", "authorization", "deployment"}:
        raise InvalidInputError("unsupported stage")
    identities = _inputs(payload.get("inputs"))
    trusted = _trusted(payload.get("trusted"))
    seed = json.dumps(
        {"boundary": boundary, "stage": stage, "inputs": identities, "trusted": trusted},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "boundary": boundary,
        "stage": stage,
        "classification": "UNKNOWN",
        "reason_codes": [],
        "affected_authorities": [],
        "inputs": identities,
        "trusted": trusted,
        "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
        "checks": {"required": [], "results": {}, "not_run": []},
        "evidence_refs": [],
        "allowed_mutations": [],
        "next_action": "stop",
        "idempotency_key": hashlib.sha256(seed).hexdigest(),
    }


def _invalid_report(payload: Any, stage: str = "preflight") -> dict[str, Any]:
    """Build an honest report even when the envelope is too malformed to bind."""
    raw = payload if isinstance(payload, Mapping) else {}
    boundary = raw.get("boundary") if raw.get("boundary") in {
        "provider-to-integration", "integration-to-site", "site-to-pages"
    } else None
    actual_stage = stage if stage in {"preflight", "qualification", "authorization", "deployment"} else None
    raw_inputs = raw.get("inputs") if isinstance(raw.get("inputs"), Mapping) else {}
    inputs = {key: value for key, value in raw_inputs.items()
              if isinstance(key, str) and isinstance(value, str)}
    raw_trusted = raw.get("trusted") if isinstance(raw.get("trusted"), Mapping) else {}
    trusted = {
        "policy_revision": raw_trusted.get("policy_revision")
        if isinstance(raw_trusted.get("policy_revision"), str) else None,
        "controller_revision": raw_trusted.get("controller_revision")
        if isinstance(raw_trusted.get("controller_revision"), str) else None,
    }
    seed = json.dumps({"boundary": boundary, "stage": actual_stage, "inputs": inputs},
                      sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": 1,
        "boundary": boundary,
        "stage": actual_stage,
        "classification": "INVALID_INPUT",
        "reason_codes": [],
        "affected_authorities": [],
        "inputs": inputs,
        "trusted": trusted,
        "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
        "checks": {"required": [], "results": {}, "not_run": []},
        "evidence_refs": [],
        "allowed_mutations": [],
        "next_action": "stop",
        "idempotency_key": hashlib.sha256(seed).hexdigest(),
    }


def _finish(report: dict[str, Any], classification: str, reasons: list[str], *, authority: str | None = None, next_action: str = "stop") -> dict[str, Any]:
    if classification not in CLASSIFICATIONS:
        raise AssertionError(classification)
    report["classification"] = classification
    report["reason_codes"] = list(dict.fromkeys(reasons))
    if authority:
        report["affected_authorities"] = [authority]
    report["next_action"] = next_action
    return report


def classify_preflight(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Classify static contract compatibility without claiming qualification."""
    try:
        report = _base_report(payload, "preflight")
        candidate = payload.get("candidate")
        consumer = payload.get("consumer")
        registry = payload.get("registry")
        if not isinstance(candidate, dict) or not isinstance(consumer, dict) or not isinstance(registry, dict):
            raise InvalidInputError("candidate, consumer and registry are required")
        providers = candidate.get("providers")
        if not isinstance(providers, dict) or set(providers) != PROVIDERS:
            raise InvalidInputError("candidate.providers must contain exactly the trusted provider set")
        for provider, revision in providers.items():
            _sha(revision, f"candidate.providers.{provider}")
            if registry.get(provider) != "TakashiSasaki/templates":
                return _finish(report, "INVALID_INPUT", ["UNTRUSTED_PROVIDER_ORIGIN"], authority=provider)

        protocol = consumer.get("protocol")
        if protocol != "publication-bundle":
            return _finish(report, "UNKNOWN", ["UNKNOWN_PROTOCOL"], authority="site")
        supported = consumer.get("supported_features")
        if not isinstance(supported, list) or any(not isinstance(item, str) for item in supported):
            raise InvalidInputError("consumer.supported_features must be an array of feature IDs")
        requirements = _requirements(candidate.get("requirements", []))
        report["requirements"]["required"] = [item.feature for item in requirements if item.required]
        report["requirements"]["supported"] = sorted(set(supported))
        missing: list[str] = []
        unsupported: list[str] = []
        fallbacks: dict[str, str] = {}
        for item in requirements:
            if item.feature in supported:
                continue
            if item.required and item.fallback == "none":
                missing.append(item.feature)
            elif item.required:
                unsupported.append(item.feature)
                fallbacks[item.feature] = item.fallback
        report["requirements"]["missing"] = missing
        report["requirements"]["unsupported"] = unsupported
        report["requirements"]["fallbacks"] = fallbacks

        destinations = candidate.get("destinations", [])
        if not isinstance(destinations, list) or any(not isinstance(item, str) for item in destinations):
            raise InvalidInputError("candidate.destinations must be an array of strings")
        if len(destinations) != len(set(destinations)):
            return _finish(report, "CROSS_PROVIDER_CONFLICT", ["DUPLICATE_DESTINATION"], authority="integration")

        if missing:
            return _finish(report, "ADAPTATION_REQUIRED", ["REQUIRED_FEATURE_UNSUPPORTED"], authority="site", next_action="adapt consumer or stop")
        if unsupported:
            return _finish(report, "ADAPTATION_REQUIRED", ["REQUIRED_FEATURE_FALLBACK_NOT_AUTHORIZED"], authority="site", next_action="adapt consumer or stop")
        report["checks"]["required"] = ["static-contract", "provider-origin", "closure", "mutation-scope"]
        report["checks"]["results"] = {name: "passed" for name in report["checks"]["required"]}
        return _finish(report, "COMPATIBLE_PENDING_QUALIFICATION", ["STATIC_CONTRACT_MATCH"], next_action="run final qualification")
    except UnknownEnvelopeError as exc:
        return _finish(_invalid_report(payload), "UNKNOWN", [str(exc)])
    except InvalidInputError as exc:
        report = _invalid_report(payload)
        return _finish(report, "INVALID_INPUT", [str(exc)])
    except CrossProviderConflictError as exc:
        return _finish(_invalid_report(payload), "CROSS_PROVIDER_CONFLICT", [str(exc)], authority="integration")


def classify_qualification(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Classify final qualification; every required check must be applied and pass."""
    preflight = classify_preflight(payload)
    if preflight["classification"] != "COMPATIBLE_PENDING_QUALIFICATION":
        preflight["stage"] = "qualification"
        return preflight
    report = _base_report(payload, "qualification")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        return _finish(report, "INVALID_INPUT", ["MISSING_CHECKS"], authority="integration")
    required = checks.get("required")
    results = checks.get("results")
    if (not isinstance(required, list) or not required
            or any(not isinstance(name, str) or not name for name in required)
            or len(set(required)) != len(required)
            or not isinstance(results, dict)
            or any(not isinstance(name, str) or not name for name in results)):
        return _finish(report, "INVALID_INPUT", ["INVALID_CHECK_SET"], authority="integration")
    report["checks"]["required"] = list(required)
    report["checks"]["results"] = dict(results)
    report["checks"]["not_run"] = [name for name in required if results.get(name) not in {"passed", "failed", "skipped"}]
    if report["checks"]["not_run"]:
        return _finish(report, "QUALIFICATION_FAILED", ["REQUIRED_CHECK_NOT_RUN"], authority="integration")
    failed = [name for name in required if results.get(name) == "failed"]
    skipped = [name for name in required if results.get(name) == "skipped"]
    if failed:
        return _finish(report, "QUALIFICATION_FAILED", ["REQUIRED_CHECK_FAILED"], authority="integration")
    if skipped:
        return _finish(report, "QUALIFICATION_FAILED", ["REQUIRED_CHECK_SKIPPED"], authority="integration")
    report["requirements"] = preflight["requirements"]
    evidence_refs = payload.get("evidence_refs", [])
    allowed_mutations = payload.get("allowed_mutations", [])
    if (not isinstance(evidence_refs, list) or any(not isinstance(item, str) for item in evidence_refs)
            or not isinstance(allowed_mutations, list)
            or any(not isinstance(item, str) for item in allowed_mutations)):
        return _finish(report, "INVALID_INPUT", ["INVALID_EVIDENCE_OR_MUTATION_LIST"], authority="integration")
    report["evidence_refs"] = list(evidence_refs)
    report["allowed_mutations"] = list(allowed_mutations)
    if payload.get("authorization") is not True:
        return _finish(report, "NOT_ELIGIBLE", ["AUTHORIZATION_NOT_GRANTED"], authority="integration", next_action="human review or activation")
    return _finish(report, "AUTO_PROCESSABLE", ["QUALIFICATION_PASSED", "AUTHORIZATION_GRANTED"], next_action="apply only the allowlisted mutation")
