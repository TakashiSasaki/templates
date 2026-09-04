from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE = (
    ROOT
    / "skills/pr-merge-gate/references/github-review-finding-representation.md"
)
DISPOSITION = ROOT / "skills/pr-merge-gate/references/review-feedback-disposition.md"
PR_REVIEW_SKILL = ROOT / "skills/pr-review/SKILL.md"
PR_REVIEW_GITHUB_REFERENCE = (
    ROOT / "skills/pr-review/references/github-pull-request-review-api.md"
)


def test_github_guidance_prefers_one_thread_per_anchorable_finding() -> None:
    text = GUIDANCE.read_text(encoding="utf-8").lower()
    required = (
        "one thread per independently actionable finding",
        "smallest changed location that introduces the root cause",
        "do not bundle unrelated defects",
        "not a rule that every finding must be inline",
    )
    for phrase in required:
        assert phrase in text


def test_github_guidance_preserves_cross_cutting_findings_outside_inline_threads() -> None:
    text = GUIDANCE.read_text(encoding="utf-8").lower()
    required = (
        "do not attach such a finding to an unrelated changed line",
        "separately identifiable in the top-level review body",
        "stable numeric finding identifiers are not required",
        "no label convention is a review-result schema",
    )
    for phrase in required:
        assert phrase in text


def test_review_acquisition_can_request_remediation_friendly_output_without_schema() -> None:
    text = GUIDANCE.read_text(encoding="utf-8").lower()
    assert "review-acquisition preference" in text
    assert "separate resolvable inline review thread" in text
    assert "do not manufacture an inline anchor" in text
    assert "provider-specific review-result object" in text
    assert "mandatory numeric finding ids" in text
    assert "github event shape as semantic review authority" in text


def test_remediation_disposition_covers_findings_without_threads() -> None:
    text = DISPOSITION.read_text(encoding="utf-8").lower()
    required = (
        "top-level finding when no thread exists",
        "validation evidence establishing the disposition",
        "material finding with no resolvable thread",
        "absence of a thread is not evidence that no unresolved finding exists",
        "do not infer resolution from a code change alone",
        "provider ui state",
    )
    for phrase in required:
        assert phrase in text


def test_generated_pr_review_sources_are_not_redefined_as_a_result_schema() -> None:
    skill = PR_REVIEW_SKILL.read_text(encoding="utf-8")
    reference = PR_REVIEW_GITHUB_REFERENCE.read_text(encoding="utf-8")

    assert "DO NOT EDIT DIRECTLY" in skill
    assert "DO NOT EDIT DIRECTLY" in reference
    assert "Do not require JSON-only output" in skill
    assert "No JSON example in this document is a review-result schema" in reference
