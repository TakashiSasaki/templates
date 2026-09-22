from __future__ import annotations

import json
from pathlib import Path


def test_feasibility_report_consistency() -> None:
    root = Path(__file__).resolve().parents[1]
    json_path = root / "docs/policy-delivery-trusted-enforcement-feasibility.json"
    md_path = root / "docs/policy-delivery-trusted-enforcement-feasibility.md"

    assert json_path.is_file(), f"missing {json_path}"
    assert md_path.is_file(), f"missing {md_path}"

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == 1
    assert data["feasibility_study"] == "policy-delivery-trusted-enforcement-c5-c7-c8"
    assert data["policy_baseline"] == "ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa"
    assert data["infrastructure_candidate"] == "3d05429778d091412a754e58e4773687e29116f7"

    # Capability qualification checks
    caps = data["current_capability_qualification"]
    assert caps["C1_worker_bootstrap"] == "ESTABLISHED"
    assert caps["C2_workspace_boundary"] == "ESTABLISHED"
    assert caps["C3_harmless_action"] == "ESTABLISHED"
    assert caps["C4_evaluator_observation"] == "ESTABLISHED"
    assert caps["C5_opaque_worker_enforcement"] == "NOT_ESTABLISHED"
    assert caps["C6_control_plane_integrity"] == "NOT_APPLICABLE"
    assert caps["C7_network_policy_enforcement"] == "NOT_ESTABLISHED"
    assert caps["C8_trial_identity_binding"] == "NOT_ESTABLISHED"
    assert caps["C9_token_usage_observability"] == "ESTABLISHED"
    assert caps["capability_decision"] == "NOT_QUALIFIED"
    assert caps["matched_trials_authorized"] is False
    assert caps["trials_run"] == 0
    assert caps["valid_matched_pairs"] == 0
    assert caps["empirical_classification"] == "NOT_ESTABLISHED"

    # Recommendation checks
    rec = data["authoritative_recommendation"]
    assert rec["decision"] == "DEFER_ENFORCEMENT_INVESTMENT"
    assert rec["platform_direction"] == "SEPARATE_GENERAL_PLATFORM_PROJECT"
    assert rec["invariants_maintained"]["default_renderer"] == "agents-md"
    assert rec["invariants_maintained"]["staged_delivery_adopted"] is False
    assert rec["invariants_maintained"]["unisolated_trials_run"] == 0

    # Markdown checks
    md_text = md_path.read_text(encoding="utf-8")
    assert "DEFER_ENFORCEMENT_INVESTMENT" in md_text
    assert "SEPARATE_GENERAL_PLATFORM_PROJECT" in md_text
    assert "NOT_ESTABLISHED" in md_text
    assert "ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa" in md_text
    assert "3d05429778d091412a754e58e4773687e29116f7" in md_text
    assert "policy-worker-boundary-v1" in md_text
