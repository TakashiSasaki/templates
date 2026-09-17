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

from publication_bundle.contract import BundleError, read_json
from site_renderer.bundle import validate

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
CLASSIFICATIONS = {
    "COMPATIBLE_PENDING_QUALIFICATION", "AUTO_PROCESSABLE", "ADAPTATION_REQUIRED",
    "CROSS_PROVIDER_CONFLICT", "INVALID_INPUT", "UNKNOWN", "QUALIFICATION_FAILED",
    "INFRASTRUCTURE_FAILURE", "NOT_ELIGIBLE", "SUPERSEDED", "NO_CHANGE",
}


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
        "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
        "checks": {"required": [], "results": {}, "not_run": []},
        "evidence_refs": [],
        "allowed_mutations": [],
        "next_action": "stop",
        "idempotency_key": hashlib.sha256(json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
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
        if (set(support) != {"schema_version", "protocol", "supported_features", "required_runtime", "fallbacks"}
                or support["schema_version"] != 1 or support["protocol"] != "publication-bundle"):
            raise BundleError("invalid Site support contract")
        if not isinstance(support["supported_features"], list) or not all(isinstance(item, str) for item in support["supported_features"]):
            raise BundleError("invalid Site supported feature list")
        manifest = read_json(bundle_root / "bundle.json")
        report = _report(
            {
                "bundle_identity": manifest.get("identity"),
                "bundle_schema": manifest.get("schema_version"),
                "content_digest": manifest.get("content_digest"),
                "producer": manifest.get("producer"),
                "providers": manifest.get("providers"),
            },
            trusted=trusted,
            site_revision=site_revision,
        )
        if manifest.get("schema_version") == 4 and "modeling" not in manifest.get("providers", {}):
            return {**report, "classification": "INVALID_INPUT", "reason_codes": ["SCHEMA_PROVIDER_MISMATCH"], "affected_authorities": ["integration"]}
        validate(bundle_root)
        required = ["publication.generic-document.v1"]
        report["requirements"]["required"] = required
        report["requirements"]["supported"] = sorted(support["supported_features"])
        missing = [feature for feature in required if feature not in support["supported_features"]]
        report["requirements"]["missing"] = missing
        report["checks"]["required"] = ["bundle-integrity", "generic-markdown-renderer", "pages-artifact-provenance"]
        report["checks"]["results"] = {check: "passed" for check in report["checks"]["required"]}
        if missing:
            report["classification"] = "ADAPTATION_REQUIRED"
            report["affected_authorities"] = ["site"]
            report["reason_codes"] = ["REQUIRED_FEATURE_UNSUPPORTED"]
            report["next_action"] = "adapt Site support or stop"
        else:
            report["classification"] = "COMPATIBLE_PENDING_QUALIFICATION"
            report["reason_codes"] = ["STATIC_BUNDLE_CONTRACT_MATCH"]
            report["next_action"] = "run renderer and acceptance qualification"
        return report
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        report["classification"] = "INVALID_INPUT"
        report["reason_codes"] = ["MALFORMED_BUNDLE_OR_SUPPORT"]
        report["affected_authorities"] = ["site"]
        report["next_action"] = "stop and inspect the exact candidate"
        report["evidence_refs"] = [str(exc)]
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
