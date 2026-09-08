from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"


def test_confirmed_review_absence_is_not_applicability_unknown() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()

    absence = (
        "when no applicable review request exists, no completed request-less result "
        "is discovered, and no other applicable review-result evidence is present"
    )
    ambiguity = (
        "if applicable review-result evidence is discovered but its cycle, purpose, "
        "or reviewed revision cannot be established"
    )

    assert absence in text
    assert "classify review evidence as absent" in text
    assert "confirmed absence is not `blocked_review_applicability_unknown`" in text
    assert "`review_evidence_pending` or `blocked_review_missing`" in text
    assert ambiguity in text
    assert text.index(absence) < text.index(ambiguity)
