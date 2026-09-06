from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skills" / "pr-merge-gate" / "references"
DISCOVERY = REFERENCES / "github-review-result-discovery.md"
REPRESENTATION = REFERENCES / "github-review-finding-representation.md"
DISPOSITION = REFERENCES / "review-feedback-disposition.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_github_adapter_inspects_all_material_review_surfaces() -> None:
    text = _text(DISCOVERY)
    for phrase in (
        "submitted pull-request reviews and their bodies",
        "ordinary pull-request or issue comments",
        "inline review comments",
        "resolvable review threads",
        "review-request / requested-reviewer state or timeline information",
        "reactions on the pull request, review comments",
        "provider-specific completion, failure, limitation, or acknowledgement signals",
    ):
        assert phrase in text


def test_github_adapter_correlates_cycle_purpose_and_revision() -> None:
    text = _text(DISCOVERY)
    for phrase in (
        "latest applicable review request",
        "do not select a request solely because it is the newest event",
        "merge-acceptance, diagnostic whole-stack, security",
        "reviewer or review system, review purpose, request cycle",
        "commit id, head sha, stack tip, or equivalent candidate identity",
        "classify the completed review as stale for exact-head merge acceptance",
        "classify applicability as unknown",
    ):
        assert phrase in text


def test_github_adapter_does_not_promote_reactions_without_contract() -> None:
    text = _text(DISCOVERY)
    assert "reaction has result semantics only when" in text
    assert "must not be promoted to completed review, approval, or `no findings`" in text
    assert "uninterpreted provider state" in text


def test_execution_classifications_distinguish_pending_findings_stale_and_unknown() -> None:
    text = _text(DISCOVERY)
    for state in (
        "review_not_requested",
        "review_pending",
        "review_complete_no_findings",
        "review_complete_with_findings",
        "review_evidence_stale",
        "review_applicability_unknown",
    ):
        assert state in text


def test_existing_adapter_references_route_through_result_discovery() -> None:
    assert "github-review-result-discovery.md" in _text(REPRESENTATION)
    disposition = _text(DISPOSITION)
    assert "github-review-result-discovery.md" in disposition
    assert "ordinary pull-request comments" in disposition
