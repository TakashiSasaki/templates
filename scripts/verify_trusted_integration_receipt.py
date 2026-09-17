#!/usr/bin/env python3
"""Re-verify the trusted Integration release receipt in a Site build job.

The Site selection job handles discovery, but it executes from the selected
Site checkout.  A deployment build therefore repeats the receipt check from a
trusted workflow checkout before it can use a promoted Integration Bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.acquire_trusted_integration_receipt import ReceiptError, acquire


SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ARCHIVE = re.compile(r"^sha256:[0-9a-f]{64}$")
BASE_FIELDS = {
    "repository", "producer", "identity", "run_id", "attempt",
    "workflow_head", "artifact_id", "archive_digest", "artifact_name",
    "trusted_receipt",
}
TRUSTED_FIELDS = {
    "artifact_id", "archive_digest", "artifact_name", "content_digest",
    "run_id", "attempt", "workflow_head", "workflow_name", "workflow_event",
    "workflow_path", "integration_revision", "bundle_identity",
    "bundle_content_digest", "policy_revision", "controller_revision",
}
PROMOTION_WORKFLOW = ".github/workflows/integration-promotion-notify.yml"
PROMOTION_NAME = "Notify Site after Integration adoption"
PROMOTION_EVENT = "pull_request"


def _json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReceiptError(f"Site trusted receipt contains duplicate field: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ReceiptError("Site trusted receipt must be a JSON object")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ReceiptError(f"{label} is not a full lowercase SHA")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ReceiptError(f"{label} is not a SHA-256 digest")
    return value


def verify(
    receipt_path: Path,
    *,
    repository: str,
    expected_integration_revision: str | None = None,
    expected_bundle_identity: str | None = None,
    expected_bundle_content_digest: str | None = None,
    expected_policy_revision: str | None = None,
    expected_controller_revision: str | None = None,
) -> dict:
    receipt = _json(receipt_path)
    if set(receipt) != BASE_FIELDS:
        raise ReceiptError("Site receipt has unsupported or missing fields")
    trusted = receipt["trusted_receipt"]
    if not isinstance(trusted, dict) or set(trusted) != TRUSTED_FIELDS:
        raise ReceiptError("Site receipt lacks the exact trusted release fields")
    if receipt.get("repository") != repository:
        raise ReceiptError("Site receipt repository mismatch")
    if receipt.get("producer") != trusted.get("integration_revision"):
        raise ReceiptError("Site receipt producer identity mismatch")
    if receipt.get("identity") != trusted.get("bundle_identity"):
        raise ReceiptError("Site receipt Bundle identity mismatch")
    if expected_integration_revision and receipt["producer"] != _sha(expected_integration_revision, "expected Integration revision"):
        raise ReceiptError("Site receipt Integration revision is not the selected lock")
    if expected_bundle_identity and receipt["identity"] != _digest(expected_bundle_identity, "expected Bundle identity"):
        raise ReceiptError("Site receipt Bundle identity is not the selected lock")
    if expected_bundle_content_digest and trusted["bundle_content_digest"] != _digest(expected_bundle_content_digest, "expected Bundle content digest"):
        raise ReceiptError("Site receipt Bundle content digest is not the selected lock")
    if not isinstance(receipt.get("run_id"), int) or receipt["run_id"] <= 0:
        raise ReceiptError("Site receipt run identity is invalid")
    if not isinstance(receipt.get("attempt"), int) or receipt["attempt"] <= 0:
        raise ReceiptError("Site receipt attempt identity is invalid")
    if receipt.get("run_id") != trusted.get("run_id") or receipt.get("attempt") != trusted.get("attempt"):
        raise ReceiptError("Site receipt run identity differs from trusted release")
    if receipt.get("workflow_head") != trusted.get("workflow_head"):
        raise ReceiptError("Site receipt workflow head differs from trusted release")
    if not isinstance(receipt.get("artifact_id"), int) or receipt["artifact_id"] <= 0:
        raise ReceiptError("Site Bundle artifact identity is invalid")
    if not isinstance(trusted.get("artifact_id"), int) or trusted["artifact_id"] <= 0:
        raise ReceiptError("trusted receipt artifact identity is invalid")
    if (trusted.get("run_id") != receipt["run_id"]
            or trusted.get("attempt") != receipt["attempt"]):
        raise ReceiptError("trusted receipt run identity differs from Bundle artifact")
    for field in ("producer", "workflow_head"):
        _sha(receipt[field], f"receipt.{field}")
    _sha(trusted["integration_revision"], "trusted integration revision")
    _sha(trusted["workflow_head"], "trusted workflow head")
    _sha(trusted["policy_revision"], "trusted Policy revision")
    _sha(trusted["controller_revision"], "trusted controller revision")
    for field in ("identity",):
        _digest(receipt[field], f"receipt.{field}")
    for field in ("content_digest", "bundle_identity", "bundle_content_digest"):
        _digest(trusted[field], f"trusted.{field}")
    if not ARCHIVE.fullmatch(receipt["archive_digest"]):
        raise ReceiptError("Bundle archive digest is invalid")
    if not ARCHIVE.fullmatch(trusted["archive_digest"]):
        raise ReceiptError("trusted receipt archive digest is invalid")
    expected_bundle_name = f"publication-bundle-{trusted['bundle_identity']}-{trusted['attempt']}-promoted"
    expected_receipt_name = f"publication-verification-{trusted['bundle_identity']}-{trusted['attempt']}-promoted"
    if receipt.get("artifact_name") != expected_bundle_name:
        raise ReceiptError("Site receipt does not select the promoted Bundle namespace")
    if trusted.get("artifact_name") != expected_receipt_name:
        raise ReceiptError("Site receipt does not select the promoted verification namespace")
    if ((trusted["workflow_name"], trusted["workflow_event"], trusted["workflow_path"])
            != (PROMOTION_NAME, PROMOTION_EVENT, PROMOTION_WORKFLOW)):
        raise ReceiptError("Site receipt workflow identity is not the approved promotion workflow")
    if ((trusted["integration_revision"], trusted["bundle_identity"])
            != (receipt["producer"], receipt["identity"])):
        raise ReceiptError("Site receipt release identity is inconsistent")
    if expected_policy_revision and trusted["policy_revision"] != _sha(expected_policy_revision, "expected Policy revision"):
        raise ReceiptError("Site receipt Policy revision is not the active pin")
    if expected_controller_revision and trusted["controller_revision"] != _sha(expected_controller_revision, "expected controller revision"):
        raise ReceiptError("Site receipt controller revision is not the active pin")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "verified-report.json"
        report = acquire(
            repository=repository,
            receipt_artifact_id=trusted["artifact_id"],
            receipt_artifact_digest=trusted["archive_digest"],
            receipt_artifact_name=trusted["artifact_name"],
            bundle_artifact_id=receipt["artifact_id"],
            bundle_artifact_digest=receipt["archive_digest"],
            bundle_artifact_name=receipt["artifact_name"],
            run_id=trusted["run_id"],
            attempt=trusted["attempt"],
            workflow_head=trusted["workflow_head"],
            workflow_name=trusted["workflow_name"],
            workflow_event=trusted["workflow_event"],
            workflow_path=trusted["workflow_path"],
            bundle_identity=trusted["bundle_identity"],
            bundle_content_digest=trusted["bundle_content_digest"],
            integration_revision=trusted["integration_revision"],
            expected_policy_revision=expected_policy_revision,
            expected_controller_revision=expected_controller_revision,
            output=output,
        )
        if hashlib.sha256(output.read_bytes()).hexdigest() != trusted["content_digest"]:
            raise ReceiptError("trusted receipt content digest changed during re-verification")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-integration-revision")
    parser.add_argument("--expected-bundle-identity")
    parser.add_argument("--expected-bundle-content-digest")
    parser.add_argument("--expected-policy-revision")
    parser.add_argument("--expected-controller-revision")
    args = parser.parse_args()
    try:
        report = verify(
            args.receipt,
            repository=args.repository,
            expected_integration_revision=args.expected_integration_revision,
            expected_bundle_identity=args.expected_bundle_identity,
            expected_bundle_content_digest=args.expected_bundle_content_digest,
            expected_policy_revision=args.expected_policy_revision,
            expected_controller_revision=args.expected_controller_revision,
        )
    except (OSError, ReceiptError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"classification": report["classification"], "trusted": report["trusted"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
