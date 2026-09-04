from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_RULE = ROOT / "policy/review/keep-findings-independently-addressable.md"
ANCHOR_RULE = ROOT / "policy/review/anchor-findings-at-cause.md"
CLOSURE_RULE = ROOT / "policy/pull-request/review-thread-closure.md"


def test_independently_actionable_findings_remain_separate_remediation_units() -> None:
    text = REVIEW_RULE.read_text(encoding="utf-8").lower()
    required = (
        "independently actionable review finding",
        "distinct remediation unit",
        "repair, explicit disposition, validation, and closure",
        "do not bundle unrelated defects",
        "provider-capability preference",
        "not a required review-result representation",
    )
    for phrase in required:
        assert phrase in text


def test_cross_cutting_findings_are_preserved_without_fabricated_anchors() -> None:
    addressability = REVIEW_RULE.read_text(encoding="utf-8").lower()
    anchoring = ANCHOR_RULE.read_text(encoding="utf-8").lower()

    assert "do not manufacture a changed-line anchor" in addressability
    assert "cross-cutting, architectural, multi-file, or multi-change findings" in addressability
    assert "separately distinguishable and independently dispositionable" in addressability
    assert "do not manufacture an inline anchor" in anchoring


def test_addressability_does_not_create_a_provider_result_schema() -> None:
    text = REVIEW_RULE.read_text(encoding="utf-8").lower()
    assert "do not require stable numeric identifiers" in text
    assert "repository-owned review-result schema" in text
    assert "provider event or object shape" in text


def test_review_closure_covers_threads_and_non_thread_findings() -> None:
    text = CLOSURE_RULE.read_text(encoding="utf-8").lower()
    required = (
        "resolvable review threads",
        "whether or not the provider exposes that finding as a resolvable thread",
        "do not mark it resolved until",
        "completed and validated for the current head",
        "code or documentation change by itself is not proof",
        "resolved ui state is bookkeeping rather than semantic proof",
        "absence of a thread does not mean the finding is resolved",
        "explicit finding-level disposition",
        "validated remediation or an explicit validated disposition",
    )
    for phrase in required:
        assert phrase in text
