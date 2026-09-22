#!/usr/bin/env python3
"""Check consistency of the Policy delivery capability probe and experiment report.

This deterministic checker asserts that:
1. The experiment baseline revision matches the landed Policy baseline.
2. The experiment infrastructure revision matches PR #1004.
3. Evaluator source and candidate artifact hashes match actual files on disk.
4. Fixture mode is non-git and .git absence is explicitly verified.
5. Required network policy is separated from host enforcement status (NOT_ESTABLISHED).
6. Capability criteria C1–C9 reflect exact evaluated statuses:
   - C1–C4, C9: ESTABLISHED
   - C6: NOT_APPLICABLE (non-git fixture)
   - C5, C7, C8: NOT_ESTABLISHED
7. The capability qualification decision is NOT_QUALIFIED.
8. Zero matched trials were run and valid matched pairs equal 0.
9. Whole-task cost metrics are UNAVAILABLE and empirical conclusion is NOT_ESTABLISHED.
10. Machine-readable JSON records and human-readable Markdown reports are fully synchronized.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_POLICY_BASELINE = "ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa"
EXPECTED_INFRASTRUCTURE_CANDIDATE = "3d05429778d091412a754e58e4773687e29116f7"
EXPECTED_EVALUATOR_SHA256 = (
    "b36eaa3a6c007a43e520ece2c581b34f006a5f8535345752ab5d42da797ef6c3"
)
EXPECTED_C8_SCHEMA = "policy-worker-boundary-v1"


class ProbeReportConsistencyError(ValueError):
    """Raised when probe evidence, baseline plan, or experiment reports are inconsistent."""


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ProbeReportConsistencyError(f"file not found: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_probe_report(root: Path = ROOT) -> dict[str, Any]:
    baseline_path = root / "docs/policy-delivery-experiment-baseline.json"
    probe_path = root / "docs/policy-delivery-capability-probe.json"
    report_json_path = root / "docs/policy-delivery-experiment-report.json"
    report_md_path = root / "docs/policy-delivery-experiment-report.md"
    matched_exp_md_path = root / "docs/policy-delivery-matched-experiment.md"

    for path, name in [
        (baseline_path, "baseline JSON"),
        (probe_path, "capability probe JSON"),
        (report_json_path, "report JSON"),
        (report_md_path, "report Markdown"),
        (matched_exp_md_path, "matched experiment Markdown"),
    ]:
        if not path.is_file():
            raise ProbeReportConsistencyError(f"missing {name}: {path}")

    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    probe_data = json.loads(probe_path.read_text(encoding="utf-8"))
    report_data = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_md_text = report_md_path.read_text(encoding="utf-8")
    matched_exp_md_text = matched_exp_md_path.read_text(encoding="utf-8")

    # 1. Baseline and Candidate Revision Invariants
    if baseline_data.get("policy_baseline", {}).get("revision") != EXPECTED_POLICY_BASELINE:
        raise ProbeReportConsistencyError(
            f"baseline plan policy revision != {EXPECTED_POLICY_BASELINE}"
        )
    infra_cand = baseline_data.get("experiment_infrastructure_candidate", {})
    if infra_cand.get("revision") != EXPECTED_INFRASTRUCTURE_CANDIDATE:
        raise ProbeReportConsistencyError(
            f"baseline plan infrastructure revision != {EXPECTED_INFRASTRUCTURE_CANDIDATE}"
        )

    if probe_data.get("policy_baseline_revision") != EXPECTED_POLICY_BASELINE:
        raise ProbeReportConsistencyError(
            f"probe policy baseline revision != {EXPECTED_POLICY_BASELINE}"
        )
    if probe_data.get("infrastructure_candidate_revision") != EXPECTED_INFRASTRUCTURE_CANDIDATE:
        raise ProbeReportConsistencyError(
            f"probe infrastructure revision != {EXPECTED_INFRASTRUCTURE_CANDIDATE}"
        )

    if report_data.get("policy_baseline", {}).get("revision") != EXPECTED_POLICY_BASELINE:
        raise ProbeReportConsistencyError(
            f"report JSON policy baseline revision != {EXPECTED_POLICY_BASELINE}"
        )
    report_infra = report_data.get("experiment_infrastructure_candidate", {})
    if report_infra.get("revision") != EXPECTED_INFRASTRUCTURE_CANDIDATE:
        raise ProbeReportConsistencyError(
            f"report JSON infrastructure revision != {EXPECTED_INFRASTRUCTURE_CANDIDATE}"
        )

    # 2. Candidate Artifacts & Evaluator Hash Verification
    evaluator_path = root / "scripts/run_matched_policy_delivery_experiment.py"
    actual_evaluator_sha = sha256_file(evaluator_path)
    if actual_evaluator_sha != EXPECTED_EVALUATOR_SHA256:
        raise ProbeReportConsistencyError(
            f"evaluator source sha256 on disk ({actual_evaluator_sha}) != expected"
        )

    candidate = baseline_data.get("candidate", {})
    if candidate.get("evaluator_source", {}).get("sha256") != EXPECTED_EVALUATOR_SHA256:
        raise ProbeReportConsistencyError(
            f"baseline candidate evaluator sha256 != {EXPECTED_EVALUATOR_SHA256}"
        )

    # 3. Fixture Mode & Git Control Plane Verification
    protocol = baseline_data.get("protocol", {})
    if protocol.get("fixture_mode") != "non-git":
        raise ProbeReportConsistencyError("baseline protocol fixture_mode must be 'non-git'")
    if not protocol.get("fixture_git_absence_verified"):
        raise ProbeReportConsistencyError(
            "baseline protocol fixture_git_absence_verified must be true"
        )

    probe_env = probe_data.get("execution_environment", {})
    if probe_env.get("fixture_mode") != "non-git":
        raise ProbeReportConsistencyError(
            "probe execution_environment fixture_mode must be 'non-git'"
        )
    if not probe_env.get("fixture_git_absence_verified"):
        raise ProbeReportConsistencyError(
            "probe execution_environment fixture_git_absence_verified must be true"
        )
    if probe_data.get("probe_execution", {}).get("git_control_plane_present") is not False:
        raise ProbeReportConsistencyError("probe git_control_plane_present must be false")

    # 4. Network Policy vs Enforcement Separation
    req_net = protocol.get("execution_model", {}).get("required_network_policy", {})
    if req_net.get("network_access") != "prohibited" or req_net.get("local_only") is not True:
        raise ProbeReportConsistencyError(
            "baseline required_network_policy must be prohibited / local_only"
        )

    qual_net = protocol.get("execution_model", {}).get("qualified_network_enforcement", {})
    if qual_net.get("status") != "NOT_ESTABLISHED":
        raise ProbeReportConsistencyError(
            "baseline qualified_network_enforcement.status must be 'NOT_ESTABLISHED'"
        )

    probe_req_net = probe_env.get("required_network_policy", {})
    if (
        probe_req_net.get("network_access") != "prohibited"
        or probe_req_net.get("local_only") is not True
    ):
        raise ProbeReportConsistencyError(
            "probe required_network_policy must be prohibited / local_only"
        )

    probe_qual_net = probe_env.get("qualified_network_enforcement", {})
    if probe_qual_net.get("status") != "NOT_ESTABLISHED":
        raise ProbeReportConsistencyError(
            "probe qualified_network_enforcement status must be 'NOT_ESTABLISHED'"
        )

    # 5. C1–C9 Qualification Criteria Statuses
    expected_statuses = {
        "C1_worker_start": "ESTABLISHED",
        "C2_tool_workspace_boundary": "ESTABLISHED",
        "C3_harmless_workspace_action": "ESTABLISHED",
        "C4_evaluator_observation": "ESTABLISHED",
        "C5_opaque_worker_enforcement": "NOT_ESTABLISHED",
        "C6_control_plane_integrity": "NOT_APPLICABLE",
        "C7_network_policy_enforcement": "NOT_ESTABLISHED",
        "C8_trial_identity_binding": "NOT_ESTABLISHED",
        "C9_token_usage_observability": "ESTABLISHED",
    }
    probe_c = probe_data.get("capability_probe", {})
    report_c = report_data.get("capability_qualification_results", {})

    for cid, expected_status in expected_statuses.items():
        if probe_c.get(cid, {}).get("status") != expected_status:
            raise ProbeReportConsistencyError(f"probe criterion {cid} status != {expected_status}")
        if report_c.get(cid, {}).get("status") != expected_status:
            raise ProbeReportConsistencyError(
                f"report JSON criterion {cid} status != {expected_status}"
            )

    # 6. Qualification Decision & Missing Facts
    if probe_data.get("decision", {}).get("capability") != "NOT_QUALIFIED":
        raise ProbeReportConsistencyError("probe capability decision must be 'NOT_QUALIFIED'")
    if report_c.get("capability_decision") != "NOT_QUALIFIED":
        raise ProbeReportConsistencyError("report capability decision must be 'NOT_QUALIFIED'")

    expected_missing = [
        "C5_opaque_worker_enforcement",
        "C7_network_policy_enforcement",
        "C8_trial_identity_binding",
    ]
    if probe_data.get("decision", {}).get("missing_facts") != expected_missing:
        raise ProbeReportConsistencyError("probe missing_facts mismatch")
    if report_c.get("missing_facts") != expected_missing:
        raise ProbeReportConsistencyError("report missing_facts mismatch")

    # 7. C8 Witness Specification
    c8_spec = protocol.get("c8_witness_specification", {})
    if c8_spec.get("schema") != EXPECTED_C8_SCHEMA:
        raise ProbeReportConsistencyError(f"C8 schema must be {EXPECTED_C8_SCHEMA}")
    if c8_spec.get("witness_status") != "absent":
        raise ProbeReportConsistencyError("C8 witness_status must be 'absent'")
    if c8_spec.get("qualification_status") != "NOT_ESTABLISHED":
        raise ProbeReportConsistencyError("C8 qualification_status must be 'NOT_ESTABLISHED'")

    # 8. Trial Execution & Cost Status
    trial_exec = report_data.get("trial_execution", {})
    if trial_exec.get("matched_trials_authorized") is not False:
        raise ProbeReportConsistencyError("matched_trials_authorized must be false")
    if trial_exec.get("trials_run") != 0:
        raise ProbeReportConsistencyError("trials_run must be 0")
    if trial_exec.get("valid_matched_pairs") != 0:
        raise ProbeReportConsistencyError("valid_matched_pairs must be 0")

    observed_costs = report_data.get("observed_whole_task_costs", {})
    if observed_costs.get("status") != "UNAVAILABLE":
        raise ProbeReportConsistencyError("observed_whole_task_costs.status must be 'UNAVAILABLE'")

    conclusion = report_data.get("empirical_conclusion", {})
    if conclusion.get("classification") != "NOT_ESTABLISHED":
        raise ProbeReportConsistencyError(
            "empirical_conclusion.classification must be 'NOT_ESTABLISHED'"
        )

    # 9. Token Accounting Consistency in Probe
    token_usage = probe_data.get("probe_execution", {}).get("observed_token_usage", {})
    inp = token_usage.get("input_tokens")
    out = token_usage.get("output_tokens")
    total = token_usage.get("total_tokens")
    if not isinstance(inp, int) or not isinstance(out, int) or not isinstance(total, int):
        raise ProbeReportConsistencyError("probe observed_token_usage must contain integers")
    if total != inp + out:
        raise ProbeReportConsistencyError(f"probe total_tokens ({total}) != {inp} + {out}")

    # 10. Digest Cross-Referencing
    actual_baseline_sha = sha256_file(baseline_path)
    actual_probe_sha = sha256_file(probe_path)
    actual_report_json_sha = sha256_file(report_json_path)

    report_artifacts = report_data.get("baseline_artifacts", {})
    plan_art = report_artifacts.get("experiment_baseline_plan", {})
    if plan_art.get("sha256") != actual_baseline_sha:
        raise ProbeReportConsistencyError(
            f"report JSON recorded baseline sha256 != actual ({actual_baseline_sha})"
        )
    probe_art = report_artifacts.get("capability_probe_record", {})
    if probe_art.get("sha256") != actual_probe_sha:
        raise ProbeReportConsistencyError(
            f"report JSON recorded capability probe sha256 != actual ({actual_probe_sha})"
        )

    # 11. Markdown Cross-Verification
    for text, name in [
        (report_md_text, "report Markdown"),
        (matched_exp_md_text, "matched experiment Markdown"),
    ]:
        if EXPECTED_POLICY_BASELINE not in text:
            raise ProbeReportConsistencyError(f"{name} missing policy baseline revision")
        if EXPECTED_INFRASTRUCTURE_CANDIDATE not in text:
            raise ProbeReportConsistencyError(f"{name} missing infrastructure revision")
        if "NOT_ESTABLISHED" not in text:
            raise ProbeReportConsistencyError(f"{name} missing NOT_ESTABLISHED")

    if actual_baseline_sha not in report_md_text:
        raise ProbeReportConsistencyError("report Markdown missing baseline JSON sha256")
    if actual_probe_sha not in report_md_text:
        raise ProbeReportConsistencyError("report Markdown missing capability probe JSON sha256")
    if actual_report_json_sha not in report_md_text:
        raise ProbeReportConsistencyError("report Markdown missing report JSON sha256")

    return {
        "status": "CONSISTENT",
        "policy_baseline": EXPECTED_POLICY_BASELINE,
        "infrastructure_candidate": EXPECTED_INFRASTRUCTURE_CANDIDATE,
        "evaluator_source_sha256": actual_evaluator_sha,
        "baseline_json_sha256": actual_baseline_sha,
        "capability_probe_json_sha256": actual_probe_sha,
        "report_json_sha256": actual_report_json_sha,
        "capability_decision": "NOT_QUALIFIED",
        "empirical_conclusion": "NOT_ESTABLISHED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check policy delivery probe report consistency.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root path.")
    arguments = parser.parse_args()
    result = check_probe_report(arguments.root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
