#!/usr/bin/env python3
"""Check the canonical clean-consumer evidence projection.

The JSON smoke manifest is the source of truth for current evaluator and
candidate identities.  The matched-experiment document contains a deliberately
small generated projection of that manifest.  This checker does not reinterpret
historical trial rows and does not make a performance claim.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs/policy-delivery-clean-consumer-smoke-final.json"
DEFAULT_DOCUMENTATION = ROOT / "docs/policy-delivery-matched-experiment.md"
BEGIN_MARKER = "<!-- BEGIN GENERATED CLEAN-CONSUMER-EVIDENCE -->"
END_MARKER = "<!-- END GENERATED CLEAN-CONSUMER-EVIDENCE -->"
SHA64 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class EvidenceConsistencyError(ValueError):
    """Raised when current evidence or its human projection is inconsistent."""


def _load_specification_module() -> Any:
    path = ROOT / "scripts" / "policy_delivery_evidence_spec.py"
    spec = importlib.util.spec_from_file_location(
        "policy_delivery_evidence_spec_for_evidence_check", path
    )
    if spec is None or spec.loader is None:
        raise EvidenceConsistencyError(f"cannot load evidence specification: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _qualification_metrics() -> dict[str, int]:
    """Derive current qualification metrics from the executable specification."""

    try:
        specification = _load_specification_module()
        model = specification.run_model_checks()
        mutations = specification.run_mutation_checks()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise EvidenceConsistencyError(
            f"cannot evaluate executable evidence specification: {exc}"
        ) from exc
    if model["violations"] or model["reachable_invariant_violations"]:
        raise EvidenceConsistencyError("executable evidence specification has violations")
    if not model["positive_state_passes"] or not all(model["witness_results"].values()):
        raise EvidenceConsistencyError("executable evidence specification lacks valid witnesses")
    if not mutations["all_detected"]:
        raise EvidenceConsistencyError("executable evidence mutations are not all detected")
    return {
        "command_domain_case_count": len(specification.command_cases()),
        "evidence_state_count": model["state_count"],
        "reachable_evidence_state_count": model["reachable_state_count"],
        "reachable_evidence_transition_count": model["reachable_transition_count"],
        "review_state_count": model["review_reachable_state_count"],
        "review_transition_count": model["review_reachable_transition_count"],
        "semantic_mutation_count": mutations["mutation_count"],
        "accepted_witness_count": sum(
            1 for passed in model["witness_results"].values() if passed
        ),
    }


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable(value: Any) -> str:
    return _sha_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _required_sha(value: Any, label: str, *, length: int = 64) -> str:
    pattern = SHA64 if length == 64 else SHA40
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise EvidenceConsistencyError(f"{label} is not a lowercase {length}-hex digest")
    return value


def _file_sha(root: Path, relative: str, label: str) -> str:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise EvidenceConsistencyError(f"{label} is not a regular file: {relative}")
    return _sha_bytes(path.read_bytes())


def _operation_text(condition: dict[str, Any]) -> str:
    operations = condition.get("operations")
    if not isinstance(operations, list) or not operations or not all(
        isinstance(value, str) for value in operations
    ):
        raise EvidenceConsistencyError("condition operations are incomplete")
    return ", ".join(operations)


def _condition_summary(name: str, condition: dict[str, Any]) -> str:
    if condition.get("clean_consumer") is not True:
        raise EvidenceConsistencyError(f"condition {name} is not a clean-consumer result")
    selected = condition.get("selected_rule_count")
    startup = condition.get("startup_rule_count")
    if not isinstance(selected, int) or not isinstance(startup, int):
        raise EvidenceConsistencyError(f"condition {name} lacks rule counts")
    if condition.get("nested_validate_render_check") is not True:
        raise EvidenceConsistencyError(f"condition {name} lacks nested validation evidence")
    if name == "C" and condition.get("nested_guidance", {}).get("succeeded") is not True:
        raise EvidenceConsistencyError("condition C lacks successful nested guidance evidence")
    return f"{selected} selected / {startup} startup; {_operation_text(condition)}"


def projection(manifest: dict[str, Any]) -> str:
    """Render the only current-identity block allowed in the documentation."""

    candidate = manifest.get("candidate")
    conditions = manifest.get("conditions")
    if not isinstance(candidate, dict) or not isinstance(conditions, dict):
        raise EvidenceConsistencyError("manifest candidate/conditions are missing")
    revision = candidate.get("revision")
    provider_tree = candidate.get("provider_tree")
    _required_sha(revision, "candidate revision", length=40)
    _required_sha(provider_tree, "provider tree", length=40)
    source = candidate.get("evaluator_source")
    spec = candidate.get("evidence_spec")
    checker = candidate.get("evidence_checker")
    projection_checker = candidate.get("evidence_projection_checker")
    external = candidate.get("external_runner")
    for value, label in (
        (source, "evaluator source"),
        (spec, "evidence specification"),
        (checker, "evidence checker"),
        (projection_checker, "evidence projection checker"),
        (external, "external runner"),
    ):
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            raise EvidenceConsistencyError(f"{label} identity is incomplete")
        _required_sha(value.get("sha256"), f"{label} hash")
    wheel = candidate.get("wheel")
    if not isinstance(wheel, str) or not wheel.endswith(".whl"):
        raise EvidenceConsistencyError("candidate wheel name is missing")
    for key in ("wheel_sha256", "wheel_payload_manifest_sha256", "runtime_lock_sha256"):
        _required_sha(candidate.get(key), f"candidate {key}")
    smoke_identity = _required_sha(
        manifest.get("smoke_result_identity"), "smoke result identity"
    )
    qualification = manifest.get("qualification")
    if not isinstance(qualification, dict):
        raise EvidenceConsistencyError("qualification metrics are missing")
    expected_identity = _stable(
        {
            "candidate": candidate,
            "conditions": conditions,
            "qualification": qualification,
        }
    )
    if smoke_identity != expected_identity:
        raise EvidenceConsistencyError(
            "smoke_result_identity does not match candidate and conditions"
        )
    if set(conditions) != {"A", "C"}:
        raise EvidenceConsistencyError("current smoke must contain exactly A and C conditions")
    a_summary = _condition_summary("A", conditions["A"])
    c_summary = _condition_summary("C", conditions["C"])
    lines = [
        BEGIN_MARKER,
        "- Candidate #998 revision: `" + revision + "`",
        "- Provider tree: `" + provider_tree + "`",
        "- Evaluator source: `" + source["path"] + "`",
        "- Evaluator SHA-256: `" + source["sha256"] + "`",
        "- Evidence specification SHA-256: `" + spec["sha256"] + "`",
        "- Evidence checker SHA-256: `" + checker["sha256"] + "`",
        "- Evidence projection checker SHA-256: `"
        + projection_checker["sha256"]
        + "`",
        "- Wheel SHA-256: `" + candidate["wheel_sha256"] + "`",
        "- Wheel manifest SHA-256: `" + candidate["wheel_payload_manifest_sha256"] + "`",
        "- Runtime lock SHA-256: `" + candidate["runtime_lock_sha256"] + "`",
        "- External runner: `" + external["path"] + "` (`" + external["sha256"] + "`)",
        "- Smoke result identity: `" + smoke_identity + "`",
        "- Qualification metrics: `"
        + "; ".join(
            f"{key}={qualification[key]}"
            for key in (
                "command_domain_case_count",
                "evidence_state_count",
                "reachable_evidence_state_count",
                "reachable_evidence_transition_count",
                "review_state_count",
                "review_transition_count",
                "semantic_mutation_count",
                "accepted_witness_count",
            )
        )
        + "`",
        "- A: " + a_summary,
        "- C: " + c_summary,
        END_MARKER,
    ]
    return "\n".join(lines)


def _validate_source_hashes(root: Path, manifest: dict[str, Any]) -> None:
    candidate = manifest["candidate"]
    for key, label in (
        ("evaluator_source", "evaluator source"),
        ("evidence_spec", "evidence specification"),
        ("evidence_checker", "evidence checker"),
        ("evidence_projection_checker", "evidence projection checker"),
    ):
        entry = candidate[key]
        actual = _file_sha(root, entry["path"], label)
        if actual != entry["sha256"]:
            raise EvidenceConsistencyError(
                f"{label} hash differs from the canonical manifest: {entry['path']}"
            )


def check(
    *,
    root: Path = ROOT,
    manifest_path: Path = DEFAULT_MANIFEST,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
) -> dict[str, str]:
    """Validate current identities and the exact generated documentation block."""

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceConsistencyError(f"cannot read evidence manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 2:
        raise EvidenceConsistencyError("unsupported evidence manifest schema")
    expected_qualification = _qualification_metrics()
    if manifest.get("qualification") != expected_qualification:
        raise EvidenceConsistencyError(
            "qualification metrics do not match the executable evidence specification"
        )
    _validate_source_hashes(root, manifest)
    expected_block = projection(manifest)
    try:
        documentation = documentation_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvidenceConsistencyError(f"cannot read evidence documentation: {exc}") from exc
    start = documentation.find(BEGIN_MARKER)
    end = documentation.find(END_MARKER)
    if start < 0 or end < 0 or end < start:
        raise EvidenceConsistencyError("generated evidence markers are missing or reordered")
    end += len(END_MARKER)
    actual_block = documentation[start:end]
    if actual_block != expected_block:
        raise EvidenceConsistencyError("documentation evidence projection is stale")
    outside = documentation[:start] + documentation[end:]
    if "The evaluator source used for this smoke has SHA-256" in outside:
        raise EvidenceConsistencyError("legacy hand-maintained evaluator identity remains")
    return {
        "smoke_result_identity": manifest["smoke_result_identity"],
        "evaluator_source_sha256": manifest["candidate"]["evaluator_source"]["sha256"],
        "candidate_revision": manifest["candidate"]["revision"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    args = parser.parse_args()
    try:
        result = check(
            root=ROOT,
            manifest_path=args.manifest,
            documentation_path=args.documentation,
        )
    except EvidenceConsistencyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
