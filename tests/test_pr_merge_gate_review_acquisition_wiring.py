from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"
GUIDANCE = (
    ROOT
    / "skills"
    / "pr-merge-gate"
    / "references"
    / "github-review-finding-representation.md"
)


def _review_acquisition_section() -> str:
    text = SKILL.read_text(encoding="utf-8")
    start = text.index("### 3. Establish independent review evidence")
    end = text.index("### 4. Clear findings and review threads")
    return text[start:end]


def test_github_review_acquisition_reaches_representation_guidance() -> None:
    section = _review_acquisition_section().lower()

    assert "references/github-review-finding-representation.md" in section
    assert "when review acquisition is github-facing" in section
    assert "one separate resolvable inline thread" in section
    assert "no bundling of unrelated findings" in section
    assert "no fabricated inline anchors" in section
    assert "separately identifiable unanchorable findings" in section


def test_acquisition_wiring_preserves_semantic_authority_boundary() -> None:
    section = _review_acquisition_section().lower()
    guidance = GUIDANCE.read_text(encoding="utf-8").lower()

    assert "provider-specific transport guidance only" in section
    assert "does not define semantic finding validity" in section
    assert "required provider result schema" in section

    assert "non-normative github integration guidance" in guidance
    assert "canonical semantic rules remain under `policy/review/`" in guidance
    assert "review-acquisition preference" in guidance
    assert "mandatory numeric finding ids" in guidance
