#!/usr/bin/env python3
"""Acquire and validate the trusted Integration receipt used by Site adoption.

The repository-dispatch event is only a wake-up signal.  This command binds the
receipt artifact to the exact successful Integration promotion run, then
validates the public receipt contract before Site qualification can proceed.
It does not execute producer code or infer trust from event payload claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile
from typing import Any, Callable


SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ARCHIVE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RECEIPT_NAME = re.compile(r"^publication-verification-[0-9a-f]{64}-[0-9]+-promoted$")
REQUIRED_VERIFICATION = {
    "schema_version", "verifier_revision", "source_report_digest",
    "workflow_run_id", "workflow_attempt", "workflow_head", "workflow_name",
    "workflow_event", "workflow_path", "artifact_id", "artifact_digest", "artifact_name",
    "bundle_identity", "bundle_content_digest", "trusted_checks",
}
TRUSTED_CHECKS = {
    "report-shape", "bundle-contract", "bundle-equivalence",
    "provider-declarations", "identity-binding",
}
REPORT_FIELDS = {
    "schema_version", "boundary", "stage", "classification", "reason_codes",
    "affected_authorities", "inputs", "trusted", "requirements", "checks",
    "evidence_refs", "allowed_mutations", "next_action", "idempotency_key",
    "verification",
}


class ReceiptError(ValueError):
    """The upstream receipt is missing, stale, or malformed."""


def api(path: str) -> dict[str, Any]:
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ReceiptError(f"{label} must be a full lowercase commit SHA")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ReceiptError(f"{label} must be a SHA-256 digest")
    return value


def _archive(value: Any, label: str) -> str:
    if not isinstance(value, str) or ARCHIVE_DIGEST.fullmatch(value) is None:
        raise ReceiptError(f"{label} must be a sha256 archive digest")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError(f"trusted receipt contains duplicate member: {key}")
        result[key] = value
    return result


def _json_bytes(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ReceiptError(f"trusted receipt contains non-standard number: {constant}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"trusted receipt is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptError("trusted receipt must be a JSON object")
    return value


def _download_report(archive: Path, *, expected_digest: str, output: Path) -> None:
    actual = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected_digest:
        raise ReceiptError("trusted receipt artifact digest mismatch")
    try:
        with zipfile.ZipFile(archive) as zipped:
            members = zipped.infolist()
            files = []
            for member in members:
                path = PurePosixPath(member.filename)
                if (path.is_absolute() or ".." in path.parts or "\\" in member.filename
                        or member.filename == "" or member.is_dir()):
                    raise ReceiptError("trusted receipt archive contains an unsafe member")
                # Reject Unix symlink entries even though the archive is read
                # as bytes; a later extraction must not change the meaning.
                if ((member.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ReceiptError("trusted receipt archive contains a symlink")
                files.append(path.as_posix())
            if files != ["verified-report.json"]:
                raise ReceiptError("trusted receipt archive inventory is not exact")
            payload = zipped.read("verified-report.json")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ReceiptError(f"unable to read trusted receipt archive: {exc}") from exc
    report = _json_bytes(payload)
    output.write_bytes(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def _validate_report(
    report: dict[str, Any],
    *,
    receipt_artifact_id: int,
    receipt_artifact_digest: str,
    receipt_artifact_name: str,
    bundle_artifact_id: int,
    bundle_artifact_digest: str,
    bundle_artifact_name: str,
    run_id: int,
    attempt: int,
    workflow_head: str,
    workflow_name: str,
    workflow_event: str,
    bundle_identity: str,
    bundle_content_digest: str,
    integration_revision: str,
    expected_policy_revision: str | None,
    expected_controller_revision: str | None,
    workflow_path: str | None = None,
) -> None:
    if set(report) != REPORT_FIELDS:
        raise ReceiptError("trusted receipt has unsupported or missing report fields")
    if report.get("schema_version") != 1 or report.get("boundary") != "provider-to-integration" or report.get("stage") != "qualification":
        raise ReceiptError("trusted receipt is not a provider qualification report")
    if report.get("classification") != "NOT_ELIGIBLE" or report.get("allowed_mutations") != []:
        raise ReceiptError("trusted receipt is not authorization-separated")
    reasons = report.get("reason_codes")
    if not isinstance(reasons, list) or any(not isinstance(value, str) for value in reasons):
        raise ReceiptError("trusted receipt reason codes are malformed")
    if not {"QUALIFICATION_PASSED", "TRUSTED_BUNDLE_EQUIVALENT"}.issubset(set(reasons)):
        raise ReceiptError("trusted receipt does not prove qualification and trusted equivalence")
    if not isinstance(report.get("evidence_refs"), list) or any(
        not isinstance(value, str) for value in report["evidence_refs"]
    ):
        raise ReceiptError("trusted receipt evidence references are malformed")
    if not isinstance(report.get("next_action"), str) or not DIGEST.fullmatch(
        str(report.get("idempotency_key", ""))
    ):
        raise ReceiptError("trusted receipt continuation identity is malformed")
    _sha(workflow_head, "workflow head")
    _sha(integration_revision, "Integration revision")
    _digest(bundle_identity, "Bundle identity")
    _digest(bundle_content_digest, "Bundle content digest")
    _archive(receipt_artifact_digest, "receipt artifact digest")
    _archive(bundle_artifact_digest, "Bundle artifact digest")
    if receipt_artifact_id <= 0 or bundle_artifact_id <= 0 or run_id <= 0 or attempt <= 0:
        raise ReceiptError("receipt artifact/run identities must be positive integers")
    if not RECEIPT_NAME.fullmatch(receipt_artifact_name):
        raise ReceiptError("trusted receipt artifact name is not the promoted namespace")
    if not isinstance(workflow_name, str) or not workflow_name.strip() or not isinstance(workflow_event, str) or not workflow_event.strip():
        raise ReceiptError("workflow identity is missing")
    verification = report.get("verification")
    if not isinstance(verification, dict) or set(verification) != REQUIRED_VERIFICATION or verification.get("schema_version") != 1:
        raise ReceiptError("trusted receipt verification shape is invalid")
    _sha(verification["verifier_revision"], "receipt verifier revision")
    _digest(verification["source_report_digest"], "source report digest")
    if not isinstance(verification["workflow_path"], str) or not verification["workflow_path"].strip():
        raise ReceiptError("trusted receipt workflow path is missing")
    if workflow_path is not None and verification["workflow_path"] != workflow_path:
        raise ReceiptError("trusted receipt workflow path mismatch")
    if expected_controller_revision and verification["verifier_revision"] != _sha(expected_controller_revision, "expected controller revision"):
        raise ReceiptError("trusted receipt verifier is not the active controller")
    if not isinstance(verification["workflow_run_id"], int) or verification["workflow_run_id"] != run_id:
        raise ReceiptError("trusted receipt run identity mismatch")
    if not isinstance(verification["workflow_attempt"], int) or verification["workflow_attempt"] != attempt:
        raise ReceiptError("trusted receipt attempt identity mismatch")
    for key, expected in (("workflow_head", workflow_head), ("workflow_name", workflow_name), ("workflow_event", workflow_event),
                          ("workflow_path", verification["workflow_path"]),
                          ("artifact_name", bundle_artifact_name), ("bundle_identity", bundle_identity),
                          ("bundle_content_digest", bundle_content_digest)):
        if verification.get(key) != expected:
            raise ReceiptError(f"trusted receipt {key} mismatch")
    if (verification.get("artifact_id") != bundle_artifact_id
            or verification.get("artifact_digest") != bundle_artifact_digest
            or verification.get("artifact_name") != bundle_artifact_name):
        raise ReceiptError("trusted receipt Bundle artifact identity mismatch")
    checks = verification.get("trusted_checks")
    if (not isinstance(checks, dict) or set(checks) != TRUSTED_CHECKS
            or any(value != "passed" for value in checks.values())):
        raise ReceiptError("trusted receipt checks are incomplete")
    inputs = report.get("inputs")
    if (not isinstance(inputs, dict)
            or inputs.get("integration_revision") != integration_revision
            or inputs.get("bundle_identity") != bundle_identity
            or inputs.get("bundle_content_digest") != bundle_content_digest):
        raise ReceiptError("trusted receipt input identity mismatch")
    trusted = report.get("trusted")
    if (not isinstance(trusted, dict)
            or set(trusted) != {"policy_revision", "controller_revision"}):
        raise ReceiptError("trusted receipt trust roots are malformed")
    trusted_controller = _sha(trusted.get("controller_revision"), "trusted controller revision")
    trusted_policy = _sha(trusted.get("policy_revision"), "trusted Policy revision")
    if verification["verifier_revision"] != trusted_controller:
        raise ReceiptError("trusted receipt verifier is not its declared controller")
    if expected_controller_revision and trusted["controller_revision"] != expected_controller_revision:
        raise ReceiptError("trusted receipt controller root mismatch")
    if expected_policy_revision and trusted_policy != _sha(expected_policy_revision, "expected Policy revision"):
        raise ReceiptError("trusted receipt Policy root mismatch")
    evidence = report.get("evidence_refs")
    required_evidence = {
        f"workflow://{workflow_name}#{run_id}/{attempt}",
        f"bundle://{bundle_identity}",
        f"trusted-bundle-equivalence://{bundle_identity}",
    }
    if not isinstance(evidence, list) or not required_evidence.issubset(set(evidence)):
        raise ReceiptError("trusted receipt evidence references are incomplete")


def acquire(
    *,
    repository: str,
    receipt_artifact_id: int,
    receipt_artifact_digest: str,
    receipt_artifact_name: str,
    bundle_artifact_id: int,
    bundle_artifact_digest: str,
    bundle_artifact_name: str,
    run_id: int,
    attempt: int,
    workflow_head: str,
    workflow_name: str,
    workflow_event: str,
    workflow_path: str | None,
    bundle_identity: str,
    bundle_content_digest: str,
    integration_revision: str,
    expected_policy_revision: str | None,
    expected_controller_revision: str | None,
    output: Path,
    api_call: Callable[[str], dict[str, Any]] = api,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ReceiptError("repository is malformed")
    prefix = f"repos/{repository}/actions"
    metadata = api_call(f"{prefix}/artifacts/{receipt_artifact_id}")
    run = api_call(f"{prefix}/runs/{run_id}/attempts/{attempt}")
    if (metadata.get("id") != receipt_artifact_id or metadata.get("expired") is not False
            or metadata.get("digest") != receipt_artifact_digest
            or metadata.get("name") != receipt_artifact_name
            or metadata.get("workflow_run", {}).get("id") != run_id
            or metadata.get("workflow_run", {}).get("head_sha") != workflow_head):
        raise ReceiptError("trusted receipt artifact metadata binding mismatch")
    if (run.get("id") != run_id or run.get("run_attempt") != attempt or run.get("head_sha") != workflow_head
            or run.get("head_repository", {}).get("full_name") != repository
            or run.get("name") != workflow_name or run.get("event") != workflow_event
            or (workflow_path is not None and run.get("path") != workflow_path)
            or run.get("status") != "completed" or run.get("conclusion") != "success"):
        raise ReceiptError("trusted receipt workflow binding mismatch")
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "receipt.zip"
        with archive.open("wb") as stream:
            subprocess.run(["gh", "api", f"{prefix}/artifacts/{receipt_artifact_id}/zip"], stdout=stream, check=True)
        _download_report(archive, expected_digest=receipt_artifact_digest, output=output)
    report = json.loads(output.read_text(encoding="utf-8"))
    _validate_report(report, receipt_artifact_id=receipt_artifact_id,
                     receipt_artifact_digest=receipt_artifact_digest,
                     receipt_artifact_name=receipt_artifact_name,
                     bundle_artifact_id=bundle_artifact_id,
                     bundle_artifact_digest=bundle_artifact_digest,
                     bundle_artifact_name=bundle_artifact_name,
                     run_id=run_id, attempt=attempt, workflow_head=workflow_head, workflow_name=workflow_name,
                     workflow_event=workflow_event, bundle_identity=bundle_identity,
                     bundle_content_digest=bundle_content_digest, integration_revision=integration_revision,
                     expected_policy_revision=expected_policy_revision, expected_controller_revision=expected_controller_revision,
                     workflow_path=workflow_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("repository", "artifact-digest", "artifact-name", "bundle-artifact-digest", "bundle-artifact-name", "workflow-head", "workflow-name", "workflow-event", "bundle-identity", "bundle-content-digest", "integration-revision"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--workflow-path")
    for name in ("artifact-id", "bundle-artifact-id", "run-id", "attempt"):
        parser.add_argument("--" + name, type=int, required=True)
    parser.add_argument("--expected-policy-revision")
    parser.add_argument("--expected-controller-revision")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        acquire(repository=args.repository, receipt_artifact_id=args.artifact_id,
                receipt_artifact_digest=args.artifact_digest, receipt_artifact_name=args.artifact_name,
                bundle_artifact_id=args.bundle_artifact_id, bundle_artifact_digest=args.bundle_artifact_digest,
                bundle_artifact_name=args.bundle_artifact_name, run_id=args.run_id, attempt=args.attempt,
                workflow_head=args.workflow_head, workflow_name=args.workflow_name, workflow_event=args.workflow_event,
                workflow_path=args.workflow_path,
                bundle_identity=args.bundle_identity, bundle_content_digest=args.bundle_content_digest,
                integration_revision=args.integration_revision, expected_policy_revision=args.expected_policy_revision,
                expected_controller_revision=args.expected_controller_revision, output=args.output)
    except (OSError, subprocess.SubprocessError, ReceiptError, ValueError) as exc:
        parser.error(str(exc))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
