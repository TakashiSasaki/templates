#!/usr/bin/env python3
"""Build and verify the reviewed handoff for an Integration promotion.

The intent records a trusted reconciliation even when the provider selection
is already present in publication-sources.json. It is not a promoted receipt;
the post-merge workflow must qualify the merged producer again.
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

from scripts.adopt_publication_sources import plan
from scripts.resolve_publication_sources import SourceLockError, read_json_object


SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ARCHIVE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
INTENT_NAME = "publication-promotion-intent.json"
WORKFLOW_PATH = ".github/workflows/integration-reconcile.yml"
PROMOTION_PR_TITLE = "chore(integration): record trusted publication intent"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase SHA-256 digest")
    return value


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    return value


def _require_artifact(value: dict[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"id", "digest", "name"}:
        raise ValueError(f"{label} identity is incomplete")
    if type(value["id"]) is not int or value["id"] <= 0:
        raise ValueError(f"{label} ID must be a positive integer")
    if not isinstance(value["digest"], str) or ARCHIVE_DIGEST.fullmatch(value["digest"]) is None:
        raise ValueError(f"{label} digest is malformed")
    if not isinstance(value["name"], str) or not value["name"]:
        raise ValueError(f"{label} name is missing")
    return value


def _canonical_json(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _git_output(repository_root: Path, arguments: list[str], label: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repository_root), *arguments],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"could not resolve {label} from the exact Git revision") from exc


def _git_text(repository_root: Path, arguments: list[str], label: str) -> str:
    try:
        return _git_output(repository_root, arguments, label).decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not valid Git text") from exc


def _committed_intent_blob(repository_root: Path, merged_revision: str) -> bytes:
    """Read the allowlisted intent from the merged revision's immutable tree."""
    entries = [
        entry for entry in _git_output(
            repository_root,
            ["ls-tree", "-z", "--full-tree", merged_revision, "--", INTENT_NAME],
            "the merged promotion-intent tree entry",
        ).split(b"\0")
        if entry
    ]
    if len(entries) != 1:
        raise ValueError("merged revision must contain exactly one promotion-intent tree entry")
    try:
        metadata, path = entries[0].split(b"\t", 1)
    except ValueError as exc:
        raise ValueError("merged promotion-intent tree entry is malformed") from exc
    fields = metadata.split()
    if len(fields) != 3 or path != INTENT_NAME.encode("utf-8"):
        raise ValueError("merged promotion-intent tree entry is malformed")
    mode, object_type, object_id = (field.decode("ascii", errors="replace") for field in fields)
    if mode != "100644":
        raise ValueError("merged promotion intent has an unexpected Git mode")
    if object_type != "blob":
        raise ValueError("merged promotion intent is not a regular Git blob")
    if SHA.fullmatch(object_id) is None:
        raise ValueError("merged promotion intent object ID is malformed")
    actual_type = _git_text(
        repository_root,
        ["cat-file", "-t", object_id],
        "the committed promotion-intent object",
    )
    if actual_type != "blob":
        raise ValueError("merged promotion intent object is not a regular Git blob")
    return _git_output(
        repository_root,
        ["cat-file", "blob", object_id],
        "the committed promotion-intent blob",
    )


def verify_live_consumer_base(*, expected_base: str, live_base: str) -> None:
    expected_base = _require_sha(expected_base, "expected Integration consumer base")
    live_base = _require_sha(live_base, "live Integration target revision")
    if live_base != expected_base:
        raise ValueError("live Integration target differs from the reconciled consumer base")


def verify_existing_promotion_pr(
    *,
    pr: dict[str, Any],
    repository_root: Path,
    repository: str,
    expected_base: str,
    expected_tree: str,
    expected_intent_digest: str,
    expected_branch: str,
    expected_idempotency_key: str,
    expected_paths: set[str],
    remote_head_ref: str,
) -> dict[str, Any]:
    """Verify every binding before reusing an existing automation PR."""
    expected_base = _require_sha(expected_base, "expected Integration consumer base")
    expected_tree = _require_sha(expected_tree, "expected deterministic mutation tree")
    expected_intent_digest = _require_digest(expected_intent_digest, "expected promotion-intent digest")
    expected_idempotency_key = _require_digest(expected_idempotency_key, "expected promotion idempotency key")
    if not isinstance(pr, dict):
        raise ValueError("existing promotion PR response is malformed")
    if pr.get("state") != "open" or pr.get("merged_at") is not None:
        raise ValueError("existing promotion PR is not open")
    if pr.get("title") != PROMOTION_PR_TITLE:
        raise ValueError("existing promotion PR title is not the deterministic promotion title")
    base = pr.get("base")
    head = pr.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise ValueError("existing promotion PR base or head binding is malformed")
    if base.get("ref") != "integration" or base.get("sha") != expected_base:
        raise ValueError("existing promotion PR base branch or base SHA is stale")
    if head.get("ref") != expected_branch:
        raise ValueError("existing promotion PR head branch is not the expected automation branch")
    head_sha = _require_sha(head.get("sha"), "existing promotion PR head SHA")
    for side, binding in (("base", base), ("head", head)):
        repo = binding.get("repo")
        if not isinstance(repo, dict) or repo.get("full_name") != repository:
            raise ValueError(f"existing promotion PR {side} repository binding is not the target repository")
    body = pr.get("body")
    if not isinstance(body, str):
        raise ValueError("existing promotion PR body is missing")
    if f"Consumer base: {expected_base}" not in body:
        raise ValueError("existing promotion PR body has a different consumer base")
    if f"Idempotency key: {expected_idempotency_key}" not in body:
        raise ValueError("existing promotion PR body has a different idempotency key")

    remote_head = _git_text(repository_root, ["rev-parse", remote_head_ref], "the automation branch tip")
    if remote_head != head_sha:
        raise ValueError("existing promotion PR head is stale relative to its automation branch")
    parent_line = _git_text(
        repository_root,
        ["rev-list", "--parents", "-n", "1", head_sha],
        "the existing promotion PR head commit",
    )
    parents = parent_line.split()
    if len(parents) != 2 or parents[1] != expected_base:
        raise ValueError("existing promotion PR head is not the exact deterministic commit on the consumer base")
    actual_tree = _git_text(repository_root, ["rev-parse", f"{head_sha}^{{tree}}"], "the existing promotion PR head tree")
    if actual_tree != expected_tree:
        raise ValueError("existing promotion PR head tree differs from the deterministic intended mutation")
    actual_paths = set(_git_text(
        repository_root,
        ["diff", "--name-only", expected_base, head_sha],
        "the existing promotion PR mutation",
    ).splitlines())
    if actual_paths != expected_paths:
        raise ValueError("existing promotion PR contains unexpected mutation paths")
    committed_intent = _git_output(
        repository_root,
        ["show", f"{head_sha}:{INTENT_NAME}"],
        "the existing promotion PR intent blob",
    )
    if _sha256(committed_intent) != expected_intent_digest:
        raise ValueError("existing promotion PR intent differs from the trusted deterministic intent")
    return pr


def _provider_tuple(lock_path: Path) -> dict[str, str]:
    lock = read_json_object(lock_path)
    publications = lock.get("publications")
    if not isinstance(publications, dict):
        raise ValueError("publication lock is missing provider selections")
    result: dict[str, str] = {}
    for name, entry in publications.items():
        if not isinstance(entry, dict):
            raise ValueError(f"publication {name} is malformed")
        result[name] = _require_sha(entry.get("revision"), f"{name} revision")
    return dict(sorted(result.items()))


def _check_report_bindings(
    *,
    current: Path,
    candidate: Path,
    source_report: Path,
    verified_report: Path,
    reconciliation_report: Path,
    producer_revision: str,
    consumer_base_revision: str,
    expected_current_lock_digest: str,
    qualification_artifact: dict[str, Any],
    trusted_controller_revision: str,
    trusted_policy_revision: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str], dict[str, str]]:
    producer_revision = _require_sha(producer_revision, "producer revision")
    consumer_base_revision = _require_sha(consumer_base_revision, "consumer base revision")
    trusted_controller_revision = _require_sha(trusted_controller_revision, "trusted controller revision")
    trusted_policy_revision = _require_sha(trusted_policy_revision, "trusted Policy revision")
    expected_current_lock_digest = _require_digest(expected_current_lock_digest, "base lock digest")
    if producer_revision != consumer_base_revision:
        raise ValueError("qualified producer must equal the Integration consumer base")
    qualification_artifact = _require_artifact(qualification_artifact, "qualification artifact")
    source_bytes = source_report.read_bytes()
    verified_bytes = verified_report.read_bytes()
    base_digest = _sha256(current.read_bytes())
    if base_digest != expected_current_lock_digest:
        raise ValueError("Integration source lock changed after the reconciliation snapshot")

    reconciliation = read_json_object(reconciliation_report)
    verified = read_json_object(verified_report)
    source = read_json_object(source_report)
    if reconciliation.get("classification") != "AUTO_PROCESSABLE":
        raise ValueError("reconciliation is not authorized to prepare a promotion intent")
    if reconciliation.get("stage") != "authorization" or reconciliation.get("boundary") != "provider-to-integration":
        raise ValueError("reconciliation report is outside the provider-to-Integration authorization boundary")
    if INTENT_NAME not in reconciliation.get("allowed_mutations", []):
        raise ValueError("reconciliation report does not allow a promotion-intent record")
    if source.get("boundary") != "provider-to-integration" or source.get("stage") != "qualification":
        raise ValueError("source report is not an Integration qualification report")
    verification = verified.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("verified qualification report has no trusted verification receipt")
    if verified.get("classification") != "NOT_ELIGIBLE" or verified.get("stage") != "qualification":
        raise ValueError("verified source report is not the expected pre-promotion qualification")
    if verification.get("source_report_digest") != _sha256(source_bytes):
        raise ValueError("trusted verification receipt is not bound to the source qualification report")
    if verification.get("schema_version") != 1:
        raise ValueError("trusted verification receipt has an unsupported schema")
    if verification.get("verifier_revision") != trusted_controller_revision:
        raise ValueError("trusted verification receipt uses a different controller pin")
    verified_trusted = verified.get("trusted")
    reconciliation_trusted = reconciliation.get("trusted")
    if not isinstance(verified_trusted, dict) or not isinstance(reconciliation_trusted, dict):
        raise ValueError("qualification or reconciliation trust identities are malformed")
    if verified_trusted.get("controller_revision") != trusted_controller_revision:
        raise ValueError("qualification report controller identity does not match the active pin")
    if verified_trusted.get("policy_revision") != trusted_policy_revision:
        raise ValueError("qualification report Policy identity does not match the active pin")
    if reconciliation_trusted.get("controller_revision") != trusted_controller_revision:
        raise ValueError("reconciliation report controller identity does not match the active pin")
    if reconciliation_trusted.get("policy_revision") != trusted_policy_revision:
        raise ValueError("reconciliation report Policy identity does not match the active pin")

    inputs = verified.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("qualification report inputs are malformed")
    if inputs.get("integration_revision") != producer_revision:
        raise ValueError("qualification producer does not match the current Integration base")
    if reconciliation.get("inputs", {}).get("integration_revision") != producer_revision:
        raise ValueError("reconciliation report producer does not match the current Integration base")
    if source.get("idempotency_key") != reconciliation.get("idempotency_key"):
        raise ValueError("reconciliation idempotency key differs from the exact qualification report")

    base_plan = plan(current, candidate)
    base_providers = _provider_tuple(candidate)
    for name, revision in base_providers.items():
        if inputs.get(f"{name}_revision") != revision:
            raise ValueError(f"qualification report does not bind candidate {name} revision")
    if inputs.get("bundle_identity") != verification.get("bundle_identity"):
        raise ValueError("qualification Bundle identity differs from its trusted receipt")
    if inputs.get("bundle_content_digest") != verification.get("bundle_content_digest"):
        raise ValueError("qualification Bundle content digest differs from its trusted receipt")
    try:
        bundle_schema = int(inputs.get("bundle_schema"))
    except (TypeError, ValueError) as exc:
        raise ValueError("qualification Bundle schema is malformed") from exc
    if bundle_schema <= 0:
        raise ValueError("qualification Bundle schema must be positive")

    bundle_artifact = _require_artifact(
        {
            "id": verification.get("artifact_id"),
            "digest": verification.get("artifact_digest"),
            "name": verification.get("artifact_name"),
        },
        "Bundle artifact",
    )
    run_id = verification.get("workflow_run_id")
    attempt = verification.get("workflow_attempt")
    if type(run_id) is not int or run_id <= 0 or type(attempt) is not int or attempt <= 0:
        raise ValueError("qualification run and attempt must be positive integers")
    for key in ("workflow_head", "workflow_name", "workflow_event", "workflow_path"):
        if not isinstance(verification.get(key), str) or not verification[key]:
            raise ValueError(f"trusted verification receipt is missing {key}")
    if verification["workflow_path"] != WORKFLOW_PATH:
        raise ValueError("qualification workflow path is not the Integration reconciliation workflow")
    if qualification_artifact["name"] != f"publication-compatibility-{verification['bundle_identity']}-{attempt}-reconciliation":
        raise ValueError("qualification report artifact name is outside the reconciliation namespace")
    if bundle_artifact["name"] != f"publication-bundle-{verification['bundle_identity']}-{attempt}-reconciliation":
        raise ValueError("Bundle artifact name is outside the reconciliation namespace")
    if not isinstance(reconciliation.get("idempotency_key"), str) or DIGEST.fullmatch(reconciliation["idempotency_key"]) is None:
        raise ValueError("reconciliation idempotency key is malformed")
    trusted_checks = verification.get("trusted_checks")
    required_trusted_checks = {
        "report-shape", "bundle-contract", "bundle-equivalence",
        "provider-declarations", "identity-binding",
    }
    if (
        not isinstance(trusted_checks, dict)
        or set(trusted_checks) != required_trusted_checks
        or any(value != "passed" for value in trusted_checks.values())
    ):
        raise ValueError("trusted qualification checks are incomplete")

    return reconciliation, verified, verification, base_providers, base_plan


def build_intent(
    *,
    current: Path,
    candidate: Path,
    source_report: Path,
    verified_report: Path,
    reconciliation_report: Path,
    producer_revision: str,
    consumer_base_revision: str,
    expected_current_lock_digest: str,
    qualification_artifact: dict[str, Any],
    trusted_controller_revision: str,
    trusted_policy_revision: str,
) -> dict[str, Any]:
    reconciliation, verified, verification, providers, base_plan = _check_report_bindings(
        current=current,
        candidate=candidate,
        source_report=source_report,
        verified_report=verified_report,
        reconciliation_report=reconciliation_report,
        producer_revision=producer_revision,
        consumer_base_revision=consumer_base_revision,
        expected_current_lock_digest=expected_current_lock_digest,
        qualification_artifact=qualification_artifact,
        trusted_controller_revision=trusted_controller_revision,
        trusted_policy_revision=trusted_policy_revision,
    )
    trusted_controller_revision = _require_sha(trusted_controller_revision, "trusted controller revision")
    trusted_policy_revision = _require_sha(trusted_policy_revision, "trusted Policy revision")
    bundle_artifact = {
        "id": verification["artifact_id"],
        "digest": verification["artifact_digest"],
        "name": verification["artifact_name"],
    }
    intent = {
        "schema_version": 1,
        "boundary": "provider-to-integration",
        "stage": "promotion-intent",
        "idempotency_key": reconciliation["idempotency_key"],
        "source_integration_revision": producer_revision,
        "consumer_base_revision": consumer_base_revision,
        "base_lock_digest": _sha256(current.read_bytes()),
        "selected_lock_digest": _sha256(candidate.read_bytes()),
        "lock_update_required": base_plan["classification"] != "NO_CHANGE",
        "provider_tuple": providers,
        "qualification_inputs": verified["inputs"],
        "bundle": {
            "schema": int(verified["inputs"]["bundle_schema"]),
            "identity": verification["bundle_identity"],
            "content_digest": verification["bundle_content_digest"],
        },
        "qualification": {
            "run_id": verification["workflow_run_id"],
            "attempt": verification["workflow_attempt"],
            "workflow_head": verification["workflow_head"],
            "workflow_name": verification["workflow_name"],
            "workflow_event": verification["workflow_event"],
            "workflow_path": verification["workflow_path"],
            "bundle_artifact": bundle_artifact,
            "qualification_artifact": qualification_artifact,
            "source_report_sha256": _sha256(source_report.read_bytes()),
            "verified_report_sha256": _sha256(verified_report.read_bytes()),
        },
        "trusted": {
            "controller_revision": trusted_controller_revision,
            "policy_revision": trusted_policy_revision,
        },
    }
    _validate_intent_shape(intent)
    return intent


def _validate_intent_shape(intent: dict[str, Any]) -> None:
    required = {
        "schema_version", "boundary", "stage", "idempotency_key",
        "source_integration_revision", "consumer_base_revision", "base_lock_digest",
        "selected_lock_digest", "lock_update_required", "provider_tuple", "qualification_inputs", "bundle",
        "qualification", "trusted",
    }
    if set(intent) != required or type(intent.get("schema_version")) is not int or intent["schema_version"] != 1:
        raise ValueError("promotion intent has an unsupported or malformed schema")
    if intent.get("boundary") != "provider-to-integration" or intent.get("stage") != "promotion-intent":
        raise ValueError("promotion intent is for the wrong publication boundary")
    _require_digest(intent.get("idempotency_key"), "promotion idempotency key")
    _require_sha(intent.get("source_integration_revision"), "source Integration revision")
    _require_sha(intent.get("consumer_base_revision"), "consumer base revision")
    _require_digest(intent.get("base_lock_digest"), "base lock digest")
    _require_digest(intent.get("selected_lock_digest"), "selected lock digest")
    if type(intent.get("lock_update_required")) is not bool:
        raise ValueError("lock_update_required must be boolean")
    if not isinstance(intent.get("provider_tuple"), dict) or not intent["provider_tuple"]:
        raise ValueError("promotion intent provider tuple is malformed")
    for name, revision in intent["provider_tuple"].items():
        if not isinstance(name, str) or not name:
            raise ValueError("promotion intent provider name is malformed")
        _require_sha(revision, f"{name} provider revision")
    bundle = intent.get("bundle")
    if not isinstance(bundle, dict) or set(bundle) != {"schema", "identity", "content_digest"}:
        raise ValueError("promotion intent Bundle identity is malformed")
    if type(bundle["schema"]) is not int or bundle["schema"] <= 0:
        raise ValueError("promotion intent Bundle schema is malformed")
    _require_digest(bundle["identity"], "Bundle identity")
    _require_digest(bundle["content_digest"], "Bundle content digest")
    expected_inputs = {
        "integration_revision": intent["source_integration_revision"],
        "bundle_schema": str(bundle["schema"]),
        "bundle_identity": bundle["identity"],
        "bundle_content_digest": bundle["content_digest"],
        **{f"{name}_revision": revision for name, revision in intent["provider_tuple"].items()},
    }
    qualification_inputs = intent.get("qualification_inputs")
    if not isinstance(qualification_inputs, dict) or qualification_inputs != expected_inputs:
        raise ValueError("promotion intent qualification inputs do not match its producer, Bundle, and provider tuple")
    expected_idempotency_key = _sha256(json.dumps(
        {
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "inputs": qualification_inputs,
            "trusted": intent.get("trusted"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))
    if intent["idempotency_key"] != expected_idempotency_key:
        raise ValueError("promotion intent idempotency key does not bind its qualification inputs and trust pins")
    qualification = intent.get("qualification")
    expected_qualification = {
        "run_id", "attempt", "workflow_head", "workflow_name", "workflow_event",
        "workflow_path", "bundle_artifact", "qualification_artifact",
        "source_report_sha256", "verified_report_sha256",
    }
    if not isinstance(qualification, dict) or set(qualification) != expected_qualification:
        raise ValueError("promotion intent qualification evidence is incomplete")
    if type(qualification["run_id"]) is not int or qualification["run_id"] <= 0:
        raise ValueError("qualification run ID is malformed")
    if type(qualification["attempt"]) is not int or qualification["attempt"] <= 0:
        raise ValueError("qualification attempt is malformed")
    _require_sha(qualification["workflow_head"], "qualification workflow head")
    for field in ("workflow_name", "workflow_event"):
        if not isinstance(qualification[field], str) or not qualification[field]:
            raise ValueError(f"qualification {field} is missing")
    if qualification["workflow_path"] != WORKFLOW_PATH:
        raise ValueError("qualification workflow path is not the Integration reconciliation workflow")
    _require_artifact(qualification["bundle_artifact"], "Bundle artifact")
    _require_artifact(qualification["qualification_artifact"], "qualification artifact")
    _require_digest(qualification["source_report_sha256"], "source report digest")
    _require_digest(qualification["verified_report_sha256"], "verified report digest")
    trusted = intent.get("trusted")
    if not isinstance(trusted, dict) or set(trusted) != {"controller_revision", "policy_revision"}:
        raise ValueError("promotion intent trust pins are incomplete")
    _require_sha(trusted["controller_revision"], "trusted controller revision")
    _require_sha(trusted["policy_revision"], "trusted Policy revision")


def verify_premerge_intent(
    *,
    intent_path: Path,
    base_lock: Path,
    selected_lock: Path,
    consumer_base_revision: str,
    trusted_controller_revision: str,
    trusted_policy_revision: str,
    branch: str,
    expected_intent_digest: str | None = None,
) -> dict[str, Any]:
    data = intent_path.read_bytes()
    if expected_intent_digest and _sha256(data) != _require_digest(expected_intent_digest, "expected intent digest"):
        raise ValueError("downloaded promotion intent differs from the trusted controller output")
    intent = json.loads(data)
    if not isinstance(intent, dict):
        raise ValueError("promotion intent must be a JSON object")
    _validate_intent_shape(intent)
    if data != _canonical_json(intent):
        raise ValueError("promotion intent is not the canonical deterministic rendering")
    consumer_base_revision = _require_sha(consumer_base_revision, "consumer base revision")
    trusted_controller_revision = _require_sha(trusted_controller_revision, "active controller revision")
    trusted_policy_revision = _require_sha(trusted_policy_revision, "active Policy revision")
    if intent["source_integration_revision"] != consumer_base_revision or intent["consumer_base_revision"] != consumer_base_revision:
        raise ValueError("promotion intent does not bind the exact Integration consumer base")
    if _sha256(base_lock.read_bytes()) != intent["base_lock_digest"]:
        raise ValueError("promotion intent base lock digest is stale")
    if _sha256(selected_lock.read_bytes()) != intent["selected_lock_digest"]:
        raise ValueError("promotion intent selected lock digest is stale")
    if _provider_tuple(selected_lock) != intent["provider_tuple"]:
        raise ValueError("promotion intent provider tuple differs from the selected lock")
    changed = plan(base_lock, selected_lock)["classification"] != "NO_CHANGE"
    if intent["lock_update_required"] is not changed:
        raise ValueError("promotion intent lock-update state is inconsistent")
    if intent["trusted"] != {
        "controller_revision": trusted_controller_revision,
        "policy_revision": trusted_policy_revision,
    }:
        raise ValueError("promotion intent trust pins do not match current activation pins")
    if branch != f"automation/publication-{intent['idempotency_key']}":
        raise ValueError("promotion branch does not match the verified idempotency key")
    return intent


def verify_merged_intent(
    *,
    repository_root: Path,
    merged_revision: str,
    trusted_controller_revision: str,
    trusted_policy_revision: str,
    branch: str,
    intent_path: Path | None = None,
) -> dict[str, Any]:
    merged_revision = _require_sha(merged_revision, "merged Integration revision")
    try:
        actual_head = subprocess.check_output(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"], text=True, stderr=subprocess.PIPE
        ).strip()
        first_parent = subprocess.check_output(
            ["git", "-C", str(repository_root), "rev-parse", f"{merged_revision}^1"], text=True, stderr=subprocess.PIPE
        ).strip()
        base_lock_bytes = subprocess.check_output(
            ["git", "-C", str(repository_root), "show", f"{first_parent}:publication-sources.json"],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError("could not resolve the merged producer and its exact Integration parent") from exc
    if actual_head != merged_revision:
        raise ValueError("producer checkout is not the exact merged Integration revision")
    # The legacy path parameter is deliberately ignored. The merged intent is
    # authoritative only when read from the exact merged Git tree.
    intent_bytes = _committed_intent_blob(repository_root, merged_revision)
    intent = json.loads(intent_bytes)
    if not isinstance(intent, dict):
        raise ValueError("promotion intent must be a JSON object")
    _validate_intent_shape(intent)
    if intent_bytes != _canonical_json(intent):
        raise ValueError("merged promotion intent is not the canonical deterministic rendering")
    trusted_controller_revision = _require_sha(trusted_controller_revision, "active controller revision")
    trusted_policy_revision = _require_sha(trusted_policy_revision, "active Policy revision")
    if intent["source_integration_revision"] != first_parent or intent["consumer_base_revision"] != first_parent:
        raise ValueError("merged producer does not have the exact reconciliation base as its first parent")
    if _sha256(base_lock_bytes) != intent["base_lock_digest"]:
        raise ValueError("merged producer parent lock differs from the promotion intent")
    selected_lock = repository_root / "publication-sources.json"
    if _sha256(selected_lock.read_bytes()) != intent["selected_lock_digest"]:
        raise ValueError("merged provider selection differs from the promotion intent")
    if _provider_tuple(selected_lock) != intent["provider_tuple"]:
        raise ValueError("merged provider tuple differs from the promotion intent")
    changed_paths = set(subprocess.check_output(
        ["git", "-C", str(repository_root), "diff", "--name-only", first_parent, merged_revision],
        text=True,
        stderr=subprocess.PIPE,
    ).splitlines())
    expected_paths = {INTENT_NAME}
    changed_lock = _sha256(base_lock_bytes) != _sha256(selected_lock.read_bytes())
    if changed_lock:
        expected_paths.add("publication-sources.json")
    if intent["lock_update_required"] is not changed_lock:
        raise ValueError("merged lock-update state differs from the promotion intent")
    if changed_paths != expected_paths:
        raise ValueError("merged promotion PR changed paths outside the exact intent and optional source lock")
    if intent["trusted"] != {
        "controller_revision": trusted_controller_revision,
        "policy_revision": trusted_policy_revision,
    }:
        raise ValueError("promotion intent trust pins changed before the merge")
    if branch != f"automation/publication-{intent['idempotency_key']}":
        raise ValueError("merged promotion branch does not match the intent idempotency key")
    return intent


def _qualification_artifact(args: argparse.Namespace) -> dict[str, Any]:
    try:
        artifact_id = int(args.qualification_artifact_id)
    except ValueError as exc:
        raise ValueError("qualification artifact ID must be an integer") from exc
    return {"id": artifact_id, "digest": args.qualification_artifact_digest, "name": args.qualification_artifact_name}


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    for argument in (
        "current", "candidate", "source-report", "verified-report", "reconciliation-report",
        "producer-revision", "consumer-base-revision", "expected-current-lock-digest",
        "qualification-artifact-id", "qualification-artifact-digest", "qualification-artifact-name",
        "trusted-controller-revision", "trusted-policy-revision", "output", "github-output",
    ):
        build.add_argument("--" + argument, required=True, type=Path if argument in {
            "current", "candidate", "source-report", "verified-report", "reconciliation-report", "output", "github-output"
        } else str)
    verify = commands.add_parser("verify")
    for argument in (
        "intent", "base-lock", "selected-lock", "consumer-base-revision",
        "trusted-controller-revision", "trusted-policy-revision", "branch", "expected-intent-digest", "github-output",
    ):
        verify.add_argument("--" + argument, required=argument not in {"expected-intent-digest", "github-output"},
                            type=Path if argument in {"intent", "base-lock", "selected-lock", "github-output"} else str)
    merged = commands.add_parser("verify-merged")
    for argument in (
        "repository-root", "merged-revision", "trusted-controller-revision", "trusted-policy-revision", "branch",
    ):
        merged.add_argument("--" + argument, required=True,
                            type=Path if argument == "repository-root" else str)
    target = commands.add_parser("verify-target")
    target.add_argument("--expected-base", required=True)
    target.add_argument("--live-base", required=True)
    pr = commands.add_parser("verify-pr")
    for argument in (
        "pr-json", "repository-root", "repository", "expected-base", "expected-tree",
        "expected-intent-digest", "expected-branch", "expected-idempotency-key", "remote-head-ref",
    ):
        pr.add_argument(
            "--" + argument,
            required=True,
            type=Path if argument in {"pr-json", "repository-root"} else str,
        )
    pr.add_argument("--expected-path", action="append", default=[])
    args = parser.parse_args()
    try:
        if args.command == "build":
            artifact = _qualification_artifact(args)
            intent = build_intent(
                current=args.current,
                candidate=args.candidate,
                source_report=args.source_report,
                verified_report=args.verified_report,
                reconciliation_report=args.reconciliation_report,
                producer_revision=args.producer_revision,
                consumer_base_revision=args.consumer_base_revision,
                expected_current_lock_digest=args.expected_current_lock_digest,
                qualification_artifact=artifact,
                trusted_controller_revision=args.trusted_controller_revision,
                trusted_policy_revision=args.trusted_policy_revision,
            )
            encoded = _canonical_json(intent)
            args.output.write_bytes(encoded)
            if args.github_output:
                with args.github_output.open("a", encoding="utf-8") as stream:
                    stream.write(f"intent_digest={_sha256(encoded)}\n")
                    stream.write(f"lock_update_required={str(intent['lock_update_required']).lower()}\n")
            print(_sha256(encoded))
        elif args.command == "verify":
            intent = verify_premerge_intent(
                intent_path=args.intent,
                base_lock=args.base_lock,
                selected_lock=args.selected_lock,
                consumer_base_revision=args.consumer_base_revision,
                trusted_controller_revision=args.trusted_controller_revision,
                trusted_policy_revision=args.trusted_policy_revision,
                branch=args.branch,
                expected_intent_digest=args.expected_intent_digest,
            )
            if args.github_output:
                with args.github_output.open("a", encoding="utf-8") as stream:
                    stream.write(f"lock_update_required={str(intent['lock_update_required']).lower()}\n")
            print("verified")
        elif args.command == "verify-merged":
            verify_merged_intent(
                repository_root=args.repository_root,
                merged_revision=args.merged_revision,
                trusted_controller_revision=args.trusted_controller_revision,
                trusted_policy_revision=args.trusted_policy_revision,
                branch=args.branch,
            )
            print("verified")
        elif args.command == "verify-target":
            verify_live_consumer_base(expected_base=args.expected_base, live_base=args.live_base)
            print("verified")
        else:
            pr_value = json.loads(args.pr_json.read_text(encoding="utf-8"))
            verify_existing_promotion_pr(
                pr=pr_value,
                repository_root=args.repository_root,
                repository=args.repository,
                expected_base=args.expected_base,
                expected_tree=args.expected_tree,
                expected_intent_digest=args.expected_intent_digest,
                expected_branch=args.expected_branch,
                expected_idempotency_key=args.expected_idempotency_key,
                expected_paths=set(args.expected_path),
                remote_head_ref=args.remote_head_ref,
            )
            print("verified")
    except (OSError, SourceLockError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
