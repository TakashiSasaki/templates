#!/usr/bin/env python3
"""Independently verify the evidence consumed by Integration reconciliation.

The qualification job is intentionally allowed to run candidate/provider code
with read-only permissions.  Its report is therefore untrusted input.  This
command runs from the trusted Integration checkout, validates the selected
Bundle with the trusted contract, checks provider declarations as data, binds
the report to the exact run/artifact identities, and emits the only receipt
that the reconciliation controller may use as a positive qualification gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integration.capabilities import CapabilityError, validate_catalog_closure, validate_provider_declaration
from publication_bundle.contract import BundleError, read_json, validate
from scripts.resolve_publication_sources import SourceLockError, read_json_object, resolve_sources


SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
PROVIDERS = ("modeling", "composition", "policy")
SUPPORTED_FEATURES = (
    "publication.generic-document.v1",
    "publication.opaque-json.v1",
    "publication.static-asset.v1",
)
REQUIRED_CHECKS = (
    "static-contract",
    "provider-origin",
    "closure",
    "mutation-scope",
    "bundle-integrity",
    "deterministic-regeneration",
    "producer-qualification",
)
REPORT_FIELDS = {
    "schema_version", "boundary", "stage", "classification", "reason_codes",
    "affected_authorities", "inputs", "trusted", "requirements", "checks",
    "evidence_refs", "allowed_mutations", "next_action", "idempotency_key",
}


class QualificationEvidenceError(ValueError):
    """Candidate evidence is malformed, stale, or not independently bound."""


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise QualificationEvidenceError(f"{label} must be a full lowercase commit SHA")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise QualificationEvidenceError(f"{label} must be a SHA-256 digest")
    return value


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = read_json(path)
    except (OSError, BundleError) as exc:
        raise QualificationEvidenceError(f"unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualificationEvidenceError(f"{label} must be a JSON object")
    return value


def _read_json(path: Path, label: str) -> Any:
    try:
        return read_json(path)
    except (OSError, BundleError) as exc:
        raise QualificationEvidenceError(f"unable to read {label}: {exc}") from exc


def _safe_provider_root(root: Path, provider: str) -> Path:
    if root.is_symlink():
        raise QualificationEvidenceError(f"{provider} checkout is not a regular directory")
    root = root.resolve()
    if not root.is_dir():
        raise QualificationEvidenceError(f"{provider} checkout is not a regular directory")
    relative = Path("docs/publication-capabilities.json")
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise QualificationEvidenceError(f"{provider} capability declaration is a symlink")
    if not current.is_file():
        raise QualificationEvidenceError(f"{provider} capability declaration is missing")
    return root


def _git_identity(root: Path, provider: str, expected: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != expected:
        raise QualificationEvidenceError(f"{provider} checkout is not bound to its selected revision")
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0 or status.stdout:
        raise QualificationEvidenceError(f"{provider} checkout is not a clean exact tree")


def _merge_requirements(declarations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for declaration in declarations.values():
        for item in declaration["requirements"]:
            feature = item["feature"]
            current = merged.setdefault(
                feature,
                {"feature": feature, "required": False, "fallback": item["fallback"]},
            )
            current["required"] = current["required"] or item["required"]
            if item["fallback"] == "none" or current["fallback"] == "none":
                current["fallback"] = "none"
            elif item["fallback"] == "generic-document":
                current["fallback"] = "generic-document"
    return [merged[name] for name in sorted(merged)]


def _bundle_counts(bundle: Path, providers: dict[str, str]) -> tuple[dict[str, int], dict[str, int]]:
    documents = _read_json(bundle / "documents.json", "Bundle documents")
    # The Bundle contract requires an array; keep this check here so the
    # capability closure check never silently treats malformed data as empty.
    if not isinstance(documents, list):
        raise QualificationEvidenceError("Bundle documents must be an array")
    document_counts = {provider: 0 for provider in providers}
    document_paths: set[str] = set()
    for item in documents:
        if not isinstance(item, dict):
            raise QualificationEvidenceError("Bundle document record is malformed")
        publication = item.get("publication")
        destination = item.get("destination")
        if publication in document_counts and isinstance(destination, str):
            document_counts[publication] += 1
            document_paths.add("publication/" + destination)
    manifest = _read_object(bundle / "bundle.json", "Bundle manifest")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise QualificationEvidenceError("Bundle manifest inventory is malformed")
    asset_counts = {provider: 0 for provider in providers}
    for path in files:
        for provider in providers:
            if path.startswith(f"publication/{provider}/") and path not in document_paths:
                asset_counts[provider] += 1
    return document_counts, asset_counts


def _validate_report_shape(report: dict[str, Any]) -> None:
    if set(report) != REPORT_FIELDS or report.get("schema_version") != 1:
        raise QualificationEvidenceError("qualification report has unsupported fields or schema")
    if report.get("boundary") != "provider-to-integration" or report.get("stage") != "qualification":
        raise QualificationEvidenceError("qualification report is not a provider qualification report")
    if report.get("classification") != "NOT_ELIGIBLE":
        raise QualificationEvidenceError(
            "candidate report must not claim adoption authorization"
        )
    if "AUTHORIZATION_NOT_GRANTED" not in report.get("reason_codes", []):
        raise QualificationEvidenceError("candidate report is missing the authorization separation reason")
    if (not isinstance(report.get("reason_codes"), list)
            or any(not isinstance(item, str) for item in report["reason_codes"])):
        raise QualificationEvidenceError("qualification reason codes are malformed")
    if (not isinstance(report.get("affected_authorities"), list)
            or any(not isinstance(item, str) for item in report["affected_authorities"])):
        raise QualificationEvidenceError("affected authorities are malformed")
    inputs = report.get("inputs")
    trusted = report.get("trusted")
    if not isinstance(inputs, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in inputs.items()):
        raise QualificationEvidenceError("qualification input identities are malformed")
    if not isinstance(trusted, dict) or set(trusted) != {"policy_revision", "controller_revision"}:
        raise QualificationEvidenceError("trusted qualification identities are malformed")
    _sha(trusted["policy_revision"], "trusted.policy_revision")
    _sha(trusted["controller_revision"], "trusted.controller_revision")
    requirements = report.get("requirements")
    if not isinstance(requirements, dict) or set(requirements) != {"required", "supported", "missing", "unsupported", "fallbacks"}:
        raise QualificationEvidenceError("qualification requirements are malformed")
    for field in ("required", "supported", "missing", "unsupported"):
        if (not isinstance(requirements[field], list)
                or any(not isinstance(item, str) for item in requirements[field])):
            raise QualificationEvidenceError(f"qualification requirements.{field} is malformed")
    if (not isinstance(requirements["fallbacks"], dict)
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in requirements["fallbacks"].items())):
        raise QualificationEvidenceError("qualification requirement fallbacks are malformed")
    checks = report.get("checks")
    if not isinstance(checks, dict) or set(checks) != {"required", "results", "not_run"}:
        raise QualificationEvidenceError("qualification checks are malformed")
    if checks["required"] != list(REQUIRED_CHECKS) or set(checks["results"]) != set(REQUIRED_CHECKS):
        raise QualificationEvidenceError("qualification checks are not the trusted required check set")
    if any(value != "passed" for value in checks["results"].values()) or checks["not_run"] != []:
        raise QualificationEvidenceError("qualification checks are incomplete or failed")
    if (not isinstance(report.get("evidence_refs"), list)
            or not report["evidence_refs"]
            or any(not isinstance(item, str) for item in report["evidence_refs"])):
        raise QualificationEvidenceError("qualification evidence references are malformed")
    if report.get("allowed_mutations") != []:
        raise QualificationEvidenceError("candidate qualification cannot grant mutations")
    if not isinstance(report.get("next_action"), str) or not DIGEST.fullmatch(report.get("idempotency_key", "")):
        raise QualificationEvidenceError("qualification continuation identity is malformed")


def _identity_key(boundary: str, inputs: dict[str, str], trusted: dict[str, str]) -> str:
    seed = json.dumps(
        {"boundary": boundary, "stage": "qualification", "inputs": inputs, "trusted": trusted},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def verify(
    *,
    report_path: Path,
    bundle: Path,
    candidate: Path,
    provider_roots: dict[str, Path],
    expected_provider_revisions: dict[str, str],
    expected_integration_revision: str,
    expected_policy_revision: str | None,
    expected_controller_revision: str,
    workflow_run_id: int,
    workflow_attempt: int,
    workflow_head: str,
    workflow_name: str,
    workflow_event: str,
    workflow_path: str,
    artifact_id: int,
    artifact_digest: str,
    artifact_name: str,
) -> dict[str, Any]:
    report = _read_object(report_path, "qualification report")
    _validate_report_shape(report)
    _sha(expected_integration_revision, "expected Integration revision")
    _sha(expected_controller_revision, "expected controller revision")
    _sha(workflow_head, "qualification workflow head")
    if not isinstance(workflow_name, str) or not workflow_name.strip():
        raise QualificationEvidenceError("qualification workflow name is missing")
    if not isinstance(workflow_event, str) or not workflow_event.strip():
        raise QualificationEvidenceError("qualification workflow event is missing")
    if not isinstance(workflow_path, str) or not workflow_path.strip():
        raise QualificationEvidenceError("qualification workflow path is missing")
    if expected_policy_revision:
        _sha(expected_policy_revision, "expected Policy revision")
    if workflow_run_id <= 0 or workflow_attempt <= 0 or artifact_id <= 0:
        raise QualificationEvidenceError("workflow and artifact identities must be positive integers")
    if not ARTIFACT_DIGEST.fullmatch(artifact_digest):
        raise QualificationEvidenceError("artifact digest is malformed")
    if not re.fullmatch(r"publication-bundle-[0-9a-f]{64}-[0-9]+-[a-z][a-z0-9-]*", artifact_name):
        raise QualificationEvidenceError("Bundle artifact name is malformed")

    selected = resolve_sources(candidate, {})
    if selected != expected_provider_revisions:
        raise QualificationEvidenceError("candidate lock does not match the selected provider tuple")
    if set(provider_roots) != set(selected):
        raise QualificationEvidenceError("provider checkout set does not match the selected tuple")
    for provider in selected:
        root = _safe_provider_root(provider_roots[provider], provider)
        _git_identity(root, provider, selected[provider])

    manifest = validate(
        bundle,
        expected_producer={"authority": "integration", "revision": expected_integration_revision},
        expected_providers=selected,
    )
    if artifact_name.split("-")[2] != manifest["identity"]:
        raise QualificationEvidenceError("Bundle artifact name is not bound to the Bundle identity")
    expected_inputs = {
        "integration_revision": expected_integration_revision,
        "bundle_schema": str(manifest["schema_version"]),
        "bundle_identity": manifest["identity"],
        "bundle_content_digest": manifest["content_digest"],
        **{f"{provider}_revision": revision for provider, revision in selected.items()},
    }
    if report["inputs"] != expected_inputs:
        raise QualificationEvidenceError("qualification report inputs do not match the trusted Bundle and lock")
    if report["trusted"]["controller_revision"] != expected_controller_revision:
        raise QualificationEvidenceError("qualification report controller identity is not trusted")
    if expected_policy_revision and report["trusted"]["policy_revision"] != expected_policy_revision:
        raise QualificationEvidenceError("qualification report Policy identity is not the active trusted pin")
    expected_evidence = {
        f"workflow://{workflow_name}#{workflow_run_id}/{workflow_attempt}",
        f"bundle://{manifest['identity']}",
        f"trusted-bundle-equivalence://{manifest['identity']}",
    }
    if not expected_evidence <= set(report["evidence_refs"]):
        raise QualificationEvidenceError("qualification report lacks exact workflow/Bundle/equivalence evidence")

    declarations = {
        provider: validate_provider_declaration(provider_roots[provider], provider)
        for provider in selected
    }
    document_counts, asset_counts = _bundle_counts(bundle, selected)
    for provider, declaration in declarations.items():
        validate_catalog_closure(
            declaration,
            document_count=document_counts[provider],
            asset_count=asset_counts[provider],
        )
    requirements = _merge_requirements(declarations)
    expected_requirements = {
        "required": [item["feature"] for item in requirements if item["required"]],
        "supported": sorted(SUPPORTED_FEATURES),
        "missing": [],
        "unsupported": [],
        "fallbacks": {},
    }
    if report["requirements"] != expected_requirements:
        raise QualificationEvidenceError("qualification requirements do not match trusted provider declarations")

    source_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    trusted = {
        "policy_revision": expected_policy_revision or report["trusted"]["policy_revision"],
        "controller_revision": expected_controller_revision,
    }
    receipt = {
        **report,
        "trusted": trusted,
        "classification": "NOT_ELIGIBLE",
        "reason_codes": list(dict.fromkeys([
            "QUALIFICATION_PASSED",
            "TRUSTED_BUNDLE_EQUIVALENT",
            "AUTHORIZATION_NOT_GRANTED",
            *([] if expected_policy_revision else ["TRUSTED_POLICY_PIN_NOT_CONFIGURED"]),
        ])),
        "next_action": "verify the trusted Policy activation grant before adoption",
        "idempotency_key": _identity_key("provider-to-integration", expected_inputs, trusted),
        "verification": {
            "schema_version": 1,
            "verifier_revision": expected_controller_revision,
            "source_report_digest": source_digest,
            "workflow_run_id": workflow_run_id,
            "workflow_attempt": workflow_attempt,
            "workflow_head": workflow_head,
            "workflow_name": workflow_name,
            "workflow_event": workflow_event,
            "workflow_path": workflow_path,
            "artifact_id": artifact_id,
            "artifact_digest": artifact_digest,
            "artifact_name": artifact_name,
            "bundle_identity": manifest["identity"],
            "bundle_content_digest": manifest["content_digest"],
            "trusted_checks": {
                "report-shape": "passed",
                "bundle-contract": "passed",
                "bundle-equivalence": "passed",
                "provider-declarations": "passed",
                "identity-binding": "passed",
            },
        },
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--composition-revision", required=True)
    parser.add_argument("--policy-root", type=Path, required=True)
    parser.add_argument("--policy-revision", required=True)
    parser.add_argument("--modeling-root", type=Path)
    parser.add_argument("--modeling-revision")
    parser.add_argument("--expected-integration-revision", required=True)
    parser.add_argument("--expected-policy-revision")
    parser.add_argument("--expected-controller-revision", required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-attempt", type=int, required=True)
    parser.add_argument("--workflow-head", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--workflow-event", required=True)
    parser.add_argument("--workflow-path", required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = {"composition": args.composition_root, "policy": args.policy_root}
    revisions = {"composition": args.composition_revision, "policy": args.policy_revision}
    if (args.modeling_root is None) != (args.modeling_revision is None):
        parser.error("--modeling-root and --modeling-revision must be supplied together")
    if args.modeling_root is not None:
        roots["modeling"] = args.modeling_root
        revisions["modeling"] = args.modeling_revision
    try:
        receipt = verify(
            report_path=args.report,
            bundle=args.bundle,
            candidate=args.candidate,
            provider_roots=roots,
            expected_provider_revisions=revisions,
            expected_integration_revision=args.expected_integration_revision,
            expected_policy_revision=args.expected_policy_revision,
            expected_controller_revision=args.expected_controller_revision,
            workflow_run_id=args.workflow_run_id,
            workflow_attempt=args.workflow_attempt,
            workflow_head=args.workflow_head,
            workflow_name=args.workflow_name,
            workflow_event=args.workflow_event,
            workflow_path=args.workflow_path,
            artifact_id=args.artifact_id,
            artifact_digest=args.artifact_digest,
            artifact_name=args.artifact_name,
        )
    except (OSError, BundleError, CapabilityError, SourceLockError, ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
