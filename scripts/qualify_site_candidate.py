#!/usr/bin/env python3
"""Run the real Site renderer and static acceptance against one candidate lock.

The candidate lock is tested in an isolated temporary committed checkout. This
keeps the source checkout read-only and makes the Site commit used by the
qualification explicit in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from site_renderer.bundle import load_lock, validate_locked


def _candidate_lock_needs_commit(candidate_site: Path, candidate_lock: Path) -> bool:
    current_lock = candidate_site / "integration-source.json"
    if current_lock.is_symlink() or candidate_lock.is_symlink():
        raise ValueError("candidate Site lock must not be a symbolic link")
    if not current_lock.is_file():
        return True
    current = load_lock(current_lock)
    candidate = load_lock(candidate_lock)
    identity_fields = ("repository", "revision", "bundle_schema", "bundle_identity", "content_digest")
    return any(current[field] != candidate[field] for field in identity_fields)


def _report(lock: dict[str, Any], *, trusted: dict[str, str | None], classification: str, reasons: list[str], checks: dict[str, str], evidence: list[str], site_revision: str | None = None, site_base_revision: str | None = None) -> dict[str, Any]:
    inputs = {
        "site_revision": site_revision,
        "site_base_revision": site_base_revision,
        "integration_revision": lock["revision"],
        "bundle_schema": str(lock["bundle_schema"]),
        "bundle_identity": lock["bundle_identity"],
        "bundle_content_digest": lock["content_digest"],
    }
    inputs = {key: value for key, value in inputs.items() if isinstance(value, str)}
    # A candidate checkout commit is an evidence identity, not a replay
    # identity.  Git timestamps and the synthetic lock commit are deliberately
    # excluded so the same Site base + selected Bundle reconciles to one key.
    replay_inputs = {key: value for key, value in inputs.items() if key != "site_revision"}
    seed = json.dumps({"boundary": "integration-to-site", "inputs": replay_inputs, "trusted": trusted}, sort_keys=True, separators=(",", ":")).encode()
    if classification == "NOT_ELIGIBLE":
        next_action = "adoption authorization is required"
    elif classification == "NO_CHANGE":
        next_action = "no Site lock mutation is required"
    else:
        next_action = "stop"
    return {
        "schema_version": 1,
        "boundary": "integration-to-site",
        "stage": "qualification",
        "classification": classification,
        "reason_codes": reasons,
        "affected_authorities": [] if classification in {"NOT_ELIGIBLE", "NO_CHANGE"} else ["site"],
        "inputs": inputs,
        "trusted": trusted,
        "requirements": {"required": ["bundle-integrity", "generic-markdown-renderer", "pages-artifact-provenance"], "supported": ["bundle-integrity", "generic-markdown-renderer", "pages-artifact-provenance"], "missing": [], "unsupported": [], "fallbacks": {}},
        "checks": {"required": list(checks), "results": checks, "not_run": [name for name, result in checks.items() if result != "passed"]},
        "evidence_refs": evidence,
        "allowed_mutations": [],
        "next_action": next_action,
        "idempotency_key": hashlib.sha256(seed).hexdigest(),
    }


def qualify(site_root: Path, bundle: Path, candidate_lock: Path, *, trusted: dict[str, str | None], evidence: list[str], candidate_root: Path | None = None) -> dict[str, Any]:
    lock = load_lock(candidate_lock)
    original_site_revision = subprocess.check_output(["git", "-C", str(site_root), "rev-parse", "HEAD"], text=True).strip()
    candidate_lock_bytes = candidate_lock.read_bytes()
    checks = {
        "bundle-integrity": "passed",
        "generic-markdown-renderer": "not-run",
        "pages-artifact-provenance": "not-run",
    }
    with tempfile.TemporaryDirectory(prefix="site-candidate-") as temporary:
        candidate_site = candidate_root or (Path(temporary) / "site")
        if candidate_root is not None and (candidate_site.exists() or candidate_site.is_symlink()):
            raise ValueError("candidate root already exists or is a symbolic link")
        build = Path(temporary) / "build"
        subprocess.run(["git", "clone", "--quiet", "--shared", str(site_root), str(candidate_site)], check=True)
        subprocess.run(["git", "-C", str(candidate_site), "checkout", "--quiet", "--detach", original_site_revision], check=True)
        current_lock = candidate_site / "integration-source.json"
        lock_changed = _candidate_lock_needs_commit(candidate_site, candidate_lock)
        if lock_changed:
            current_lock.write_bytes(candidate_lock_bytes)
            subprocess.run(["git", "-C", str(candidate_site), "config", "user.email", "publication-controller@users.noreply.github.com"], check=True)
            subprocess.run(["git", "-C", str(candidate_site), "config", "user.name", "publication-controller"], check=True)
            subprocess.run(["git", "-C", str(candidate_site), "add", "integration-source.json"], check=True)
            subprocess.run(["git", "-C", str(candidate_site), "commit", "--quiet", "-m", "dry-run: bind candidate Integration Bundle"], check=True)
        candidate_revision = subprocess.check_output(["git", "-C", str(candidate_site), "rev-parse", "HEAD"], text=True).strip()
        subprocess.run([
            sys.executable, str(candidate_site / "scripts/render_publication_bundle.py"),
            "--bundle", str(bundle), "--bundle-identity", lock["bundle_identity"],
            "--site-root", str(candidate_site), "--output", str(build),
            "--public-url", "https://templates.moukaeritai.work/",
        ], check=True)
        checks["generic-markdown-renderer"] = "passed"
        from scripts.check_audience_artifact import check_artifact
        from scripts.check_bundle_reader import check as check_reader
        from scripts.check_site_artifact import check as check_artifact_contract
        check_artifact(build / "site", bundle, candidate_site / "integration-source.json")
        check_reader(build / "site", bundle, lock)
        check_artifact_contract(build / "site", bundle, lock)
        checks["pages-artifact-provenance"] = "passed"
        classification = "NO_CHANGE" if not lock_changed else "NOT_ELIGIBLE"
        reasons = ["ALREADY_SELECTED"] if not lock_changed else ["AUTHORIZATION_NOT_GRANTED"]
        result = _report(lock, trusted=trusted, classification=classification, reasons=reasons, checks=checks, evidence=evidence + [f"site-candidate://{candidate_revision}"], site_revision=candidate_revision, site_base_revision=original_site_revision)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, default=Path("."))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--candidate-lock", type=Path, required=True)
    parser.add_argument(
        "--candidate-root",
        type=Path,
        help="Optional persistent checkout for dry-runs; the qualified candidate revision remains available for artifact rendering",
    )
    parser.add_argument("--trusted-policy-revision")
    parser.add_argument("--trusted-controller-revision")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trusted = {"policy_revision": args.trusted_policy_revision or None, "controller_revision": args.trusted_controller_revision or None}
    try:
        report = qualify(args.site_root, args.bundle, args.candidate_lock, trusted=trusted, evidence=args.evidence_ref, candidate_root=args.candidate_root)
    except Exception as exc:
        report = _report(load_lock(args.candidate_lock), trusted=trusted, classification="QUALIFICATION_FAILED", reasons=["SITE_QUALIFICATION_FAILED"], checks={"bundle-integrity": "passed", "generic-markdown-renderer": "failed", "pages-artifact-provenance": "not-run"}, evidence=args.evidence_ref + [type(exc).__name__], site_revision=None)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["classification"])
    return 0 if report["classification"] == "NOT_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
