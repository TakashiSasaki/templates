from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "policy" / "pull-request" / "review-result-applicability.md"
PROFILE = ROOT / "profiles" / "pull-request.yml"
INDEPENDENT = ROOT / "policy" / "pull-request" / "independent-exact-head-review.md"
REACQUISITION = ROOT / "policy" / "pull-request" / "review-reacquisition-after-disposition.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_review_result_classification_is_bound_to_latest_applicable_cycle() -> None:
    text = _text(RULE)
    for phrase in (
        "latest applicable review request",
        "review purpose being evaluated",
        "bind the classification to that review cycle",
        "older completed review",
        "later applicable request that is still pending",
        "does not supersede a different purpose merely because its request is newer",
    ):
        assert phrase in text


def test_revision_applicability_is_fail_closed_and_exact_head_for_merge_acceptance() -> None:
    text = _text(RULE)
    for phrase in (
        "reviewed commit, head sha, stack identity, or other revision binding",
        "compare that binding with the current proposed candidate",
        "independent exact-head rule",
        "requires the exact current proposed head",
        "completed review is stale for merge acceptance",
        "keep the affected completion or no-findings conclusion fail-closed",
    ):
        assert phrase in text


def test_historical_findings_survive_review_cycle_and_head_changes_when_applicable() -> None:
    text = _text(RULE)
    for phrase in (
        "review-cycle completion applicability and finding applicability are distinct",
        "earlier review cycle must not by itself establish completion",
        "material actionable finding reported earlier remains part of the known finding backlog",
        "do not discard a finding solely because the head changed or a newer review request exists",
    ):
        assert phrase in text


def test_pull_request_profile_selects_applicability_rule() -> None:
    assert "policy/pull-request/review-result-applicability.md" in _text(PROFILE)


def test_existing_exact_head_and_reacquisition_rules_reference_applicability() -> None:
    assert "review-result applicability rule" in _text(INDEPENDENT)
    reacquisition = _text(REACQUISITION)
    assert "review-result applicability rule" in reacquisition
    assert "diagnostic purpose" in reacquisition
    assert "merge-acceptance review cycle" in reacquisition
