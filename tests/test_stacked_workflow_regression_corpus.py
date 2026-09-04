from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ROOT
    / "tests"
    / "fixtures"
    / "stacked-workflow-regressions"
    / "cases.json"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8").lower()


def _load_planner() -> ModuleType:
    path = ROOT / "scripts" / "plan_policy_release_chain.py"
    spec = importlib.util.spec_from_file_location(
        "stacked_regression_release_planner",
        path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empirical_corpus_contains_exactly_the_five_observed_defect_classes() -> None:
    corpus = json.loads(CASES.read_text(encoding="utf-8"))
    assert corpus["schema_version"] == 1
    assert {case["id"] for case in corpus["cases"]} == {
        "A-provider-cannot-establish-cumulative-binding",
        "B-lower-semantic-candidate-changes",
        "C-lower-pr-merge-preserves-reviewed-tree",
        "D-final-whole-stack-audit",
        "E-immutable-merge-ci-release-safeguards",
    }
    assert all(
        case["condition"] and len(case["expected"]) >= 3
        for case in corpus["cases"]
    )


def test_case_a_incomplete_cumulative_binding_falls_back_fail_closed_without_loop() -> None:
    policy = _text("policy/pull-request/stacked-review-coverage.md")
    gate = _text("skills/pr-merge-gate/references/stacked-review-coverage.md")
    assert "tip-only review" in policy
    assert "keeps merge authorization fail-closed" in policy
    assert "use the ordinary individual exact-head review path" in policy
    assert "do not repeatedly request cumulative clarification" in policy
    assert "fall back to individual exact-head review" in gate


def test_case_b_lower_semantic_change_stales_downstream_chain_before_review() -> None:
    planner = _load_planner()
    plan = planner.build_plan(ROOT, toolchain_revision="a" * 40)
    assert plan["stale_stages"][-3:] == [
        "S-installer-candidate",
        "I-policy-publication",
        "policy-to-site-projection",
    ]
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]
    stacked = _text(
        "skills/orchestrate-repository-change/references/stacked-pr-workflow.md"
    )
    assert "do not deliberately review a knowingly intermediate" in stacked


def test_case_c_lower_merge_reuses_only_evidence_with_established_applicability() -> None:
    stacked_policy = _text("policy/pull-request/stacked-review-coverage.md")
    freshness = _text("policy/pull-request/target-branch-head-freshness.md")
    reuse = _text("policy/pull-request/reuse-valid-evidence.md")
    assert "without mechanically invalidating all evidence" in stacked_policy
    assert (
        "without mechanically invalidating all evidence or requiring an "
        "upper-head rewrite solely for base movement"
    ) in stacked_policy
    assert (
        "do not require proposed-head synchronization solely because the target "
        "branch moved"
    ) in freshness
    assert "target-branch movement" in reuse
    assert "does not by itself invalidate unrelated" in reuse


def test_case_d_whole_stack_audit_waits_for_ci_and_stays_architectural() -> None:
    stacked = _text(
        "skills/orchestrate-repository-change/references/stacked-pr-workflow.md"
    )
    assert "architecture/dependency/completeness audit" in stacked
    assert "required ci" in stacked
    assert "completed successfully" in stacked
    assert "pending required ci blocks the final review request" in stacked
    expected_scope = (
        "dependency",
        "overlap or gaps",
        "design consistency",
        "final-state behavior",
        "test sufficiency",
        "unintended scope",
    )
    for phrase in expected_scope:
        assert phrase in stacked
    assert "not lower-member merge evidence" in stacked
    assert "cumulative multi-member acceptance review is optional" in stacked


def test_case_e_exact_head_ci_merge_and_full_sha_release_guards_remain_intact() -> None:
    merge_guard = _text("policy/pull-request/immutable-head-guard.md")
    ci = _text("policy/pull-request/exact-head-ci-evidence.md")
    release = _text("repository-policy/release-trust.md")
    assert "bind the operation to the exact proposed head commit" in merge_guard
    assert (
        "rely only on ci or validation evidence that applies to that exact head commit"
        in ci
    )
    assert "never replace an executable identity with a mutable branch or tag" in release
    assert "full-sha" in release

    planner = _load_planner()
    identities = planner.current_identities(ROOT)
    assert all(FULL_SHA.fullmatch(value) for value in identities.values())
    descriptor_path = ROOT / "release" / "skill-installer.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert descriptor["installer"]["revision"] == identities["I"]
    assert descriptor["skill_source"]["revision"] == identities["S"]
