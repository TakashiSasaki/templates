from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent_policy.policy_loader import load_rules, parse_policy

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/pull-request.yml"
POLICY_DIR = ROOT / "policy/pull-request"

EXPECTED = [
    "pull-request.require-explicit-stacked-review-coverage",
    "pull-request.verify-target-branch-head-freshness",
    "pull-request.preflight-review-acquisition",
    "pull-request.require-independent-exact-head-review",
    "pull-request.close-review-threads-before-merge",
    "pull-request.require-exact-head-ci-evidence",
    "pull-request.fail-closed-on-unresolved-ci-discovery",
    "pull-request.reuse-valid-exact-head-evidence",
    "pull-request.require-current-mergeability",
    "pull-request.refresh-live-state-before-merge",
    "pull-request.guard-merge-against-head-movement",
    "pull-request.verify-merge-result",
]


def _rule_id(path: Path) -> str:
    source = path.relative_to(ROOT).as_posix()
    return parse_policy(path, source, "toolchain").id


def _metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing YAML front matter: {path}"
    _, frontmatter, _body = text.split("---\n", 2)
    data = yaml.safe_load(frontmatter)
    assert isinstance(data, dict), f"invalid YAML front matter: {path}"
    return data


def test_pull_request_profile_is_closed_and_atomic() -> None:
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    paths = [ROOT / path for path in profile["policy_files"]]
    assert [path.parent for path in paths] == [POLICY_DIR] * len(paths)
    assert all(path.is_file() for path in paths)
    assert [_rule_id(path) for path in paths] == EXPECTED
    actual_files = sorted(path.name for path in POLICY_DIR.glob("*.md"))
    profile_files = sorted(path.name for path in paths)
    assert actual_files == profile_files


def test_pull_request_policy_metadata_schema() -> None:
    metadata = [_metadata(path) for path in sorted(POLICY_DIR.glob("*.md"))]
    required = {"id", "severity", "overridable", "order"}

    assert metadata
    assert all(required.issubset(item) for item in metadata)
    assert all(isinstance(item["id"], str) and item["id"] for item in metadata)
    assert all(
        isinstance(item["severity"], str) and item["severity"]
        for item in metadata
    )
    assert all(type(item["overridable"]) is bool for item in metadata)
    assert all(type(item["order"]) is int for item in metadata)

    orders = [item["order"] for item in metadata]
    assert len(orders) == len(set(orders))


def test_pull_request_profile_composes_with_coding_and_review_contexts() -> None:
    coding = load_rules(ROOT, ["core", "security-baseline", "pull-request"], [])
    review = load_rules(
        ROOT,
        ["core", "security-baseline", "review", "pull-request"],
        [],
    )
    for rules in (coding, review):
        rule_ids = [rule.id for rule in rules]
        assert len(rule_ids) == len(set(rule_ids))
        assert set(EXPECTED).issubset(rule_ids)


def test_independent_review_rule_fails_closed_for_missing_or_stale_review() -> None:
    rule = (POLICY_DIR / "independent-exact-head-review.md").read_text(
        encoding="utf-8"
    )
    required_semantics = (
        "at least one completed review",
        "exact proposed head commit",
        "zero completed reviews is not review evidence",
        "must block merge",
        "self-review",
        "review metadata",
        "treat the review as stale",
        "blocked rather than waiving the requirement",
        "must not invent or self-authorize one",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_independent_review_rule_requires_demonstrably_complete_analysis() -> None:
    rule = (POLICY_DIR / "independent-exact-head-review.md").read_text(
        encoding="utf-8"
    )
    required_semantics = (
        "provider-recorded review object is not by itself evidence",
        "applicable review procedure or review contract",
        "required analysis completed for the exact proposed head",
        "incomplete, partial, failed, or materially limited",
        "must not satisfy the independent-review requirement",
        "provider records that review as submitted or completed",
        "cannot establish whether the required analysis completed",
        "keep merge authorization fail-closed",
        "absence of blocking findings",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_exact_head_ci_rule_rejects_stale_or_unresolved_evidence() -> None:
    rule = (POLICY_DIR / "exact-head-ci-evidence.md").read_text(encoding="utf-8")
    required_semantics = (
        "current proposed head",
        "exact head commit",
        "older head is historical evidence",
        "one live query returns no result",
        "keep merge authorization fail-closed",
        "newest applicable evidence",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_ci_discovery_rule_requires_correlated_read_only_evidence() -> None:
    rule = (POLICY_DIR / "ci-discovery-fail-closed.md").read_text(encoding="utf-8")
    required_semantics = (
        "unresolved discovery",
        "continue read-only discovery",
        "single empty query",
        "only one live index",
        "elapsed time alone",
        "corroborating current evidence",
        "positively identified",
        "do not re-enter discovery merely for conservatism",
        "concrete invalidation signal",
        "do not mutate the pull request or proposed head solely to manufacture new ci evidence",
        "keep merge authorization blocked",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_valid_evidence_reuse_is_mandatory_and_selective() -> None:
    rule = (POLICY_DIR / "reuse-valid-evidence.md").read_text(encoding="utf-8")
    required_semantics = (
        "reuse that evidence while the facts that bind it remain unchanged",
        "repeated observations",
        "extra review cycles",
        "waiting periods",
        "redundant evidence collection",
        "must not silently enlarge the acceptance baseline",
        "reacquire only the evidence affected by a concrete invalidation signal",
        "target-branch movement requires impact evaluation",
        "does not by itself invalidate unrelated exact-head evidence",
        "elapsed time alone does not invalidate exact-head evidence",
        "fail closed",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_target_branch_movement_invalidates_only_affected_evidence() -> None:
    rule = (POLICY_DIR / "target-branch-head-freshness.md").read_text(
        encoding="utf-8"
    )
    required_semantics = (
        "current target branch full commit sha",
        "evaluate the proposed change against that exact target state",
        "inspect the intervening target change",
        "synchronize or rebuild the proposed head only when",
        "do not require proposed-head synchronization solely because the target branch moved",
        "does not by itself invalidate unrelated exact-head ci or review evidence",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_final_merge_rules_require_live_state_and_immutable_head_guard() -> None:
    mergeability = (POLICY_DIR / "current-mergeability.md").read_text(encoding="utf-8")
    refresh = (POLICY_DIR / "final-live-state-refresh.md").read_text(encoding="utf-8")
    guard = (POLICY_DIR / "immutable-head-guard.md").read_text(encoding="utf-8")

    for semantic in (
        "immediately before merge authorization",
        "current repository state",
        "mergeability is unknown, false, or changes",
    ):
        assert semantic.lower() in mergeability.lower()

    for semantic in (
        "immediately before authorizing or executing",
        "current proposed head",
        "current target-branch head",
        "current review state",
        "unresolved review-thread state",
        "current mergeability",
        "do not unconditionally reacquire exact-head validation",
        "re-evaluate only the acceptance evidence affected",
        "concrete invalidation signal",
    ):
        assert semantic.lower() in refresh.lower()

    for semantic in (
        "exact proposed head commit",
        "strongest supported immutable-head precondition",
        "must not silently apply to a different head",
        "cannot enforce an immutable proposed-head precondition",
        "do not retry blindly",
    ):
        assert semantic.lower() in guard.lower()


def test_post_merge_rule_separates_merge_from_release_readiness() -> None:
    rule = (POLICY_DIR / "post-merge-verification.md").read_text(encoding="utf-8")
    required_semantics = (
        "pull request is actually merged",
        "record the resulting merge identity",
        "target branch contains the intended merged result",
        "without a transport error",
        "does not by itself establish those later states",
    )
    for semantic in required_semantics:
        assert semantic.lower() in rule.lower()


def test_pull_request_rules_are_provider_and_actor_neutral() -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in POLICY_DIR.glob("*.md")
    )
    implementation_terms = (
        "Antigravity",
        "Codex",
        "Gemini",
        "GitHub",
        "GitLab",
        "Bitbucket",
        "expected_head_sha",
        "check-run",
        "check-suite",
        "automated actor",
        "LEFT",
        "RIGHT",
        "REQUEST_CHANGES",
    )
    for term in implementation_terms:
        assert term not in corpus


def test_stacked_review_coverage_is_explicit_and_fail_closed() -> None:
    rule = (POLICY_DIR / "stacked-review-coverage.md").read_text(
        encoding="utf-8"
    ).lower()
    required_semantics = (
        "integration base exact sha",
        "ordered stack membership",
        "each member exact head sha",
        "stack tip exact sha",
        "cumulative reviewed scope",
        "review contract",
        "reviewer independence",
        "review completion state",
        "material limitations",
        "tip-only review",
        "must not infer",
        "member exact head changes",
        "stack ordering changes",
        "integration base changes",
        "cumulative scope changes",
        "review contract changes",
        "fail closed",
    )
    for semantic in required_semantics:
        assert semantic in rule
