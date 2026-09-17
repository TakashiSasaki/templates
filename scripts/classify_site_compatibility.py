#!/usr/bin/env python3
"""Classify a candidate Bundle against the trusted Site support contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publication_bundle.contract import BundleError, read_json, regular, validate_requirements
from site_renderer.bundle import validate

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
CLASSIFICATIONS = {
    "COMPATIBLE_PENDING_QUALIFICATION", "AUTO_PROCESSABLE", "ADAPTATION_REQUIRED",
    "CROSS_PROVIDER_CONFLICT", "INVALID_INPUT", "UNKNOWN", "QUALIFICATION_FAILED",
    "INFRASTRUCTURE_FAILURE", "NOT_ELIGIBLE", "SUPERSEDED", "NO_CHANGE",
}
GENERIC_DOCUMENT = "publication.generic-document.v1"


class UnknownCompatibility(ValueError):
    """The trusted classifier does not implement the supplied major contract."""


def _validate_support(support: Any) -> None:
    if not isinstance(support, dict):
        raise BundleError("Site support contract must be an object")
    schema_version = support.get("schema_version")
    if type(schema_version) is not int:
        raise BundleError("Site support schema_version must be an integer")
    if schema_version != 1:
        raise UnknownCompatibility("unsupported Site support contract major version")
    if set(support) != {"schema_version", "protocol", "supported_features", "required_runtime", "fallbacks"}:
        raise BundleError("invalid Site support contract fields")
    if support["protocol"] != "publication-bundle":
        raise UnknownCompatibility("unsupported Site support protocol")
    features = support["supported_features"]
    runtime = support["required_runtime"]
    fallbacks = support["fallbacks"]
    if (not isinstance(features, list) or not features
            or not all(isinstance(item, str) for item in features)
            or len(set(features)) != len(features)):
        raise BundleError("invalid Site supported feature list")
    if (not isinstance(runtime, list) or not runtime
            or not all(isinstance(item, str) for item in runtime)
            or len(set(runtime)) != len(runtime)):
        raise BundleError("invalid Site runtime support list")
    if not isinstance(fallbacks, dict):
        raise BundleError("invalid Site fallback contract")
    if (any(not isinstance(key, str) or value not in {"none", "generic-document", "ignore"}
                   for key, value in fallbacks.items())):
        raise BundleError("invalid Site fallback contract")


def _legacy_requirements(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep the v3 reader contract explicit until the Site lock cuts over."""
    providers = manifest.get("providers")
    if not isinstance(providers, dict):
        raise BundleError("Bundle providers are not an object")
    return [
        {"provider": provider, "feature": GENERIC_DOCUMENT, "required": True, "fallback": "generic-document"}
        for provider in ("composition", "policy")
    ]


def _evaluate_requirements(
    manifest: dict[str, Any], support: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str], dict[str, str]]:
    if manifest["schema_version"] == 4:
        closure = manifest["requirements"]
    else:
        closure = _legacy_requirements(manifest)
    validate_requirements(closure, manifest["providers"])
    supported = set(support["supported_features"])
    required: list[str] = []
    missing: list[str] = []
    unsupported: list[str] = []
    fallbacks: dict[str, str] = {}
    for requirement in closure:
        feature = requirement["feature"]
        key = f"{requirement['provider']}:{feature}"
        if requirement["required"] and feature not in required:
            required.append(feature)
        if feature in supported:
            continue
        producer_fallback = requirement["fallback"]
        declared_fallback = support["fallbacks"].get(feature)
        allowed = False
        if producer_fallback == "generic-document":
            allowed = (declared_fallback == "generic-document" and GENERIC_DOCUMENT in supported)
        elif producer_fallback == "ignore":
            allowed = (not requirement["required"] and declared_fallback == "ignore")
        if allowed:
            fallbacks[key] = producer_fallback
            continue
        if feature not in unsupported:
            unsupported.append(feature)
        if requirement["required"] and feature not in missing:
            missing.append(feature)
    return closure, required, missing, unsupported, fallbacks


def _report(
    bundle: dict[str, Any],
    stage: str = "preflight",
    *,
    trusted: dict[str, str | None] | None = None,
    site_revision: str | None = None,
) -> dict[str, Any]:
    identity = bundle.get("bundle_identity") or bundle.get("identity")
    producer = bundle.get("producer") if isinstance(bundle.get("producer"), dict) else {}
    providers = bundle.get("providers") if isinstance(bundle.get("providers"), dict) else {}
    inputs = {
        "integration_revision": producer.get("revision"),
        "bundle_schema": str(bundle.get("bundle_schema")) if bundle.get("bundle_schema") is not None else None,
        "bundle_identity": identity,
        "bundle_content_digest": bundle.get("content_digest"),
        "requirements_digest": bundle.get("requirements_digest"),
        "site_revision": site_revision,
    }
    inputs.update({f"{name}_revision": revision for name, revision in providers.items()})
    return {
        "schema_version": 1,
        "boundary": "integration-to-site",
        "stage": stage,
        "classification": "UNKNOWN",
        "reason_codes": [],
        "affected_authorities": [],
        "inputs": {key: value for key, value in inputs.items() if isinstance(value, str)},
        "trusted": trusted or {"policy_revision": None, "controller_revision": None},
        "requirements": {"closure": [], "required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
        "checks": {"required": [], "results": {}, "not_run": []},
        "evidence_refs": [],
        "allowed_mutations": [],
        "next_action": "stop",
        "idempotency_key": hashlib.sha256(json.dumps({
            "boundary": "integration-to-site",
            "inputs": {key: value for key, value in inputs.items() if key != "site_revision"},
            "trusted": trusted or {"policy_revision": None, "controller_revision": None},
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }


def classify(
    bundle_root: Path,
    *,
    support_path: Path,
    trusted: dict[str, str | None] | None = None,
    site_revision: str | None = None,
) -> dict[str, Any]:
    payload = {"bundle_identity": "", "trusted": trusted}
    report = _report(payload, trusted=trusted, site_revision=site_revision)
    try:
        support = read_json(support_path)
        _validate_support(support)
        manifest = read_json(regular(bundle_root, "bundle.json"))
        if not isinstance(manifest, dict):
            raise BundleError("Bundle manifest must be an object")
        schema_version = manifest.get("schema_version")
        if type(schema_version) is not int:
            raise BundleError("Bundle schema_version must be an integer")
        report = _report(
            {
                "bundle_identity": manifest.get("identity"),
                "bundle_schema": schema_version,
                "content_digest": manifest.get("content_digest"),
                "producer": manifest.get("producer"),
                "providers": manifest.get("providers"),
                "requirements_digest": manifest.get("requirements_digest"),
            },
            trusted=trusted,
            site_revision=site_revision,
        )
        if schema_version not in {3, 4}:
            raise UnknownCompatibility("unsupported Bundle schema major version")
        manifest = validate(bundle_root)
        closure, required, missing, unsupported, fallbacks = _evaluate_requirements(manifest, support)
        report["requirements"]["closure"] = closure
        report["requirements"]["required"] = required
        report["requirements"]["supported"] = sorted(support["supported_features"])
        report["requirements"]["missing"] = missing
        report["requirements"]["unsupported"] = unsupported
        report["requirements"]["fallbacks"] = fallbacks
        report["checks"]["required"] = list(support["required_runtime"])
        report["checks"]["results"] = {
            "bundle-integrity": "passed"
        } if "bundle-integrity" in report["checks"]["required"] else {}
        report["checks"]["not_run"] = [
            check for check in report["checks"]["required"]
            if check not in report["checks"]["results"]
        ]
        if missing or unsupported:
            report["classification"] = "ADAPTATION_REQUIRED"
            report["affected_authorities"] = ["site"]
            report["reason_codes"] = ["REQUIRED_FEATURE_UNSUPPORTED" if missing else "OPTIONAL_FEATURE_UNSUPPORTED"]
            report["next_action"] = "adapt Site support or stop"
        else:
            report["classification"] = "COMPATIBLE_PENDING_QUALIFICATION"
            report["reason_codes"] = ["STATIC_BUNDLE_CONTRACT_MATCH"]
            report["next_action"] = "run renderer and acceptance qualification"
        return report
    except UnknownCompatibility as exc:
        report["classification"] = "UNKNOWN"
        report["reason_codes"] = ["UNKNOWN_CONTRACT_VERSION_OR_PROTOCOL"]
        report["affected_authorities"] = ["site"]
        report["next_action"] = "stop and inspect the trusted contract reader"
        report["evidence_refs"] = [str(exc)]
        return report
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        report["classification"] = "INVALID_INPUT"
        report["reason_codes"] = ["MALFORMED_BUNDLE_OR_SUPPORT"]
        report["affected_authorities"] = ["site"]
        report["next_action"] = "stop and inspect the exact candidate"
        report["evidence_refs"] = [str(exc)]
        return report
    except Exception as exc:
        report["classification"] = "UNKNOWN"
        report["reason_codes"] = ["UNEXPECTED_CLASSIFIER_ERROR", type(exc).__name__]
        report["affected_authorities"] = ["site"]
        report["next_action"] = "stop and inspect the trusted classifier"
        report["evidence_refs"] = [type(exc).__name__]
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--support", type=Path, default=Path("contracts/site-publication-support.json"))
    parser.add_argument("--trusted-policy-revision")
    parser.add_argument("--trusted-controller-revision")
    parser.add_argument("--site-revision")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trusted = {
        "policy_revision": args.trusted_policy_revision,
        "controller_revision": args.trusted_controller_revision,
    }
    report = classify(args.bundle, support_path=args.support, trusted=trusted, site_revision=args.site_revision)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["classification"] == "COMPATIBLE_PENDING_QUALIFICATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
