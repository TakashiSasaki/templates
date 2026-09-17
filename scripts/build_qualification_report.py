#!/usr/bin/env python3
"""Create the Integration-owned structured report for an exact Bundle.

This command is deliberately evidence-only.  It never edits a provider lock,
creates a pull request, or grants authorization.  The default Shadow mode
therefore produces NOT_ELIGIBLE even when every qualification check passes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integration.capabilities import normalize_requirement_closure, validate_provider_declaration
from integration.compatibility import classify_qualification
from publication_bundle.contract import read_json


PROVIDERS = ("modeling", "composition", "policy")
FEATURES = (
    "publication.generic-document.v1",
    "publication.opaque-json.v1",
    "publication.static-asset.v1",
)


def _requirements(roots: dict[str, Path], providers: tuple[str, ...]) -> list[dict[str, Any]]:
    declarations = {
        provider: validate_provider_declaration(roots[provider], provider)
        for provider in providers
    }
    return normalize_requirement_closure(declarations, providers)


def _destinations(bundle: Path) -> list[str]:
    documents = read_json(bundle / "documents.json")
    if not isinstance(documents, list):
        raise ValueError("Bundle documents model must be an array")
    destinations = []
    for item in documents:
        if not isinstance(item, dict) or not isinstance(item.get("destination"), str):
            raise ValueError("Bundle document destination is malformed")
        destinations.append(item["destination"])
    return destinations


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    bundle = read_json(args.bundle / "bundle.json")
    producer = bundle.get("producer")
    if producer != {"authority": "integration", "revision": args.integration_revision}:
        raise ValueError("Bundle producer identity does not match the qualification input")
    providers = read_json(args.bundle / "provenance.json").get("providers")
    if not isinstance(providers, dict) or frozenset(providers) not in {
        frozenset({"composition", "policy"}),
        frozenset({"modeling", "composition", "policy"}),
    }:
        raise ValueError("qualification report requires an approved exact provider tuple")
    provider_names = tuple(name for name in PROVIDERS if name in providers)
    roots = {provider: Path(getattr(args, f"{provider}_root")) for provider in provider_names}
    requirements = _requirements(roots, provider_names)
    if bundle.get("schema_version") == 4:
        from publication_bundle.contract import requirements_digest
        if bundle.get("requirements") != requirements or bundle.get("requirements_digest") != requirements_digest(requirements):
            raise ValueError("Bundle requirement closure does not match provider declarations")
    provider_registry = {provider: "TakashiSasaki/templates" for provider in provider_names}
    inputs = {
        "integration_revision": args.integration_revision,
        "bundle_schema": str(bundle["schema_version"]),
        **{f"{provider}_revision": providers[provider] for provider in provider_names},
        "bundle_identity": bundle["identity"],
        "bundle_content_digest": bundle["content_digest"],
    }
    checks = [
        "static-contract",
        "provider-origin",
        "closure",
        "mutation-scope",
        "bundle-integrity",
        "deterministic-regeneration",
        "producer-qualification",
    ]
    return {
        "boundary": "provider-to-integration",
        "inputs": inputs,
        "trusted": {
            "policy_revision": args.trusted_policy_revision,
            "controller_revision": args.trusted_controller_revision,
        },
        "candidate": {
            "providers": providers,
            "requirements": requirements,
            "destinations": _destinations(args.bundle),
        },
        "consumer": {"protocol": "publication-bundle", "supported_features": list(FEATURES)},
        "registry": provider_registry,
        "checks": {"required": checks, "results": {name: "passed" for name in checks}},
        "authorization": False,
        "evidence_refs": list(args.evidence_ref),
        "allowed_mutations": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--integration-revision", required=True)
    for provider in PROVIDERS:
        parser.add_argument(f"--{provider}-root", type=Path)
    parser.add_argument("--trusted-policy-revision", required=True)
    parser.add_argument("--trusted-controller-revision", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = classify_qualification(build_payload(args))
    except Exception as exc:  # a report generator must fail closed, never claim success
        report = {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "classification": "UNKNOWN",
            "reason_codes": ["UNEXPECTED_REPORT_GENERATOR_ERROR"],
            "affected_authorities": ["integration"],
            "inputs": {},
            "trusted": {"policy_revision": None, "controller_revision": None},
            "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
            "checks": {"required": [], "results": {}, "not_run": []},
            "evidence_refs": [type(exc).__name__],
            "allowed_mutations": [],
            "next_action": "stop",
            "idempotency_key": "0" * 64,
        }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["classification"])
    return 0 if report["classification"] in {"COMPATIBLE_PENDING_QUALIFICATION", "AUTO_PROCESSABLE", "NO_CHANGE", "NOT_ELIGIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
