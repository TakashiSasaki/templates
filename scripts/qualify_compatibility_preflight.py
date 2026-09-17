#!/usr/bin/env python3
"""Build and classify the cheap Integration contract preflight.

This command reads only the exact, already materialized provider checkouts and
the trusted Integration contract.  It does not generate a Publication Bundle,
run Site code, or grant authorization.  The workflow uses its report as a
positive gate before deterministic Bundle qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integration.capabilities import validate_provider_declaration
from integration.compatibility import classify_preflight
from integration.git import checked_revision
from integration.publication_model import load_catalog, parse_manifest, read_json


PROVIDERS = ("modeling", "composition", "policy")
BASE_PROVIDERS = ("composition", "policy")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
FEATURES = (
    "publication.generic-document.v1",
    "publication.opaque-json.v1",
    "publication.static-asset.v1",
)


def _sha(value: str, label: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    return value


def _requirements(roots: dict[str, Path], names: tuple[str, ...]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for provider in names:
        declaration = validate_provider_declaration(roots[provider], provider)
        for item in declaration["requirements"]:
            current = merged.setdefault(
                item["feature"],
                {"feature": item["feature"], "required": False, "fallback": item["fallback"]},
            )
            current["required"] = current["required"] or item["required"]
            if item["fallback"] == "none" or current["fallback"] == "none":
                current["fallback"] = "none"
            elif item["fallback"] == "generic-document":
                current["fallback"] = "generic-document"
    return [merged[name] for name in sorted(merged)]


def _destinations(
    integration_root: Path,
    provider_roots: dict[str, Path],
    names: tuple[str, ...],
) -> list[str]:
    """Project declared catalog destinations into Bundle paths for collision checks."""
    manifest = parse_manifest(
        read_json(integration_root / "site-manifest.json", "Site manifest")
    )
    destinations = {
        (PurePosixPath("publication") / item["destination"]).as_posix()
        for item in manifest.documents
    }
    catalogs: dict[str, tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]] = {}
    for provider in names:
        catalogs[provider] = load_catalog(provider, provider_roots[provider])
        _, assets = catalogs[provider]
        for asset in assets:
            destinations.add(
                (
                    PurePosixPath("publication")
                    / provider
                    / PurePosixPath(asset["destination"])
                ).as_posix()
            )

    # Bundle v4 mechanically adds Modeling document routes to the existing
    # generic navigation projection.  Include those routes in the same static
    # collision set without importing Site or executing provider code.
    if "modeling" in names:
        documents, _ = catalogs["modeling"]
        for document_id in documents:
            destination = (
                "modeling/index.md"
                if document_id == "catalog"
                else f"modeling/resources/{document_id}.md"
            )
            destinations.add((PurePosixPath("publication") / destination).as_posix())
    return sorted(destinations)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    integration_root = args.integration_root.resolve(strict=True)
    integration_revision = _sha(args.integration_revision, "Integration revision")
    if checked_revision(integration_root) != integration_revision:
        raise ValueError("Integration checkout revision differs from the exact preflight input")
    provider_roots: dict[str, Path] = {
        "composition": args.composition_root.resolve(strict=True),
        "policy": args.policy_root.resolve(strict=True),
    }
    provider_revisions = {
        "composition": _sha(args.composition_revision, "Composition revision"),
        "policy": _sha(args.policy_revision, "Policy revision"),
    }
    if args.modeling_root is not None or args.modeling_revision is not None:
        if args.modeling_root is None or args.modeling_revision is None:
            raise ValueError("Modeling root and revision must be supplied together")
        provider_roots["modeling"] = args.modeling_root.resolve(strict=True)
        provider_revisions["modeling"] = _sha(args.modeling_revision, "Modeling revision")

    provider_revisions = {
        provider: provider_revisions[provider]
        for provider in PROVIDERS
        if provider in provider_revisions
    }

    names = tuple(provider for provider in PROVIDERS if provider in provider_roots)
    if frozenset(names) not in {frozenset(BASE_PROVIDERS), frozenset(PROVIDERS)}:
        raise ValueError("preflight requires an approved exact provider tuple")
    for provider in names:
        actual = checked_revision(provider_roots[provider])
        if actual != provider_revisions[provider]:
            raise ValueError(
                f"{provider} checkout revision differs from the exact preflight input"
            )

    declarations = {
        provider: validate_provider_declaration(provider_roots[provider], provider)
        for provider in names
    }
    # Reading every catalog here forces the typed inventory and source closure
    # checks to run before the producer's deterministic generation starts.
    for provider in names:
        load_catalog(provider, provider_roots[provider])
    requirements = _requirements(provider_roots, names)
    return {
        "boundary": "provider-to-integration",
        "inputs": {
            "integration_revision": integration_revision,
            "bundle_schema": "4" if "modeling" in names else "3",
            **{f"{provider}_revision": provider_revisions[provider] for provider in names},
        },
        "trusted": {
            "policy_revision": _sha(args.trusted_policy_revision, "trusted Policy revision"),
            "controller_revision": _sha(args.trusted_controller_revision, "trusted controller revision"),
        },
        "candidate": {
            "providers": provider_revisions,
            "requirements": requirements,
            "destinations": _destinations(integration_root, provider_roots, names),
        },
        "consumer": {
            "protocol": "publication-bundle",
            # This is the current Integration contract, not a provider claim.
            # A newly declared feature must be added to this list and its
            # downstream Site contract before it can cross this boundary.
            "supported_features": list(FEATURES),
        },
        "registry": {provider: "TakashiSasaki/templates" for provider in names},
        "evidence_refs": list(args.evidence_ref),
        "allowed_mutations": [],
        "declarations": {
            provider: {
                "exports": declaration["exports"],
                "export_features": declaration["export_features"],
            }
            for provider, declaration in declarations.items()
        },
    }


def _fallback(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    inputs: dict[str, str] = {}
    for name, value in (
        ("integration_revision", args.integration_revision),
        ("composition_revision", args.composition_revision),
        ("policy_revision", args.policy_revision),
        ("modeling_revision", args.modeling_revision),
    ):
        if isinstance(value, str) and FULL_SHA.fullmatch(value):
            inputs[name] = value
    seed = json.dumps(
        {"boundary": "provider-to-integration", "stage": "preflight", "inputs": inputs},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "boundary": "provider-to-integration",
        "stage": "preflight",
        "classification": "INVALID_INPUT",
        "reason_codes": ["INVALID_PREFLIGHT_INPUT", reason],
        "affected_authorities": ["integration"],
        "inputs": inputs,
        "trusted": {"policy_revision": None, "controller_revision": None},
        "requirements": {
            "required": [],
            "supported": [],
            "missing": [],
            "unsupported": [],
            "fallbacks": {},
        },
        "checks": {"required": [], "results": {}, "not_run": []},
        "evidence_refs": list(args.evidence_ref),
        "allowed_mutations": [],
        "next_action": "stop and inspect the exact provider contract input",
        "idempotency_key": hashlib.sha256(seed).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-root", type=Path, required=True)
    parser.add_argument("--integration-revision", required=True)
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--composition-revision", required=True)
    parser.add_argument("--policy-root", type=Path, required=True)
    parser.add_argument("--policy-revision", required=True)
    parser.add_argument("--modeling-root", type=Path)
    parser.add_argument("--modeling-revision")
    parser.add_argument("--trusted-policy-revision", required=True)
    parser.add_argument("--trusted-controller-revision", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = classify_preflight(build_payload(args))
    except Exception as exc:
        report = _fallback(args, type(exc).__name__)
        report["evidence_refs"].append(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(report["classification"])
    return 0 if report["classification"] == "COMPATIBLE_PENDING_QUALIFICATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
