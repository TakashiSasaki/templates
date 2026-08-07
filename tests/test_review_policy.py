from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/review.yml"
REVIEW_DIR = ROOT / "policy/review"
DOC = ROOT / "docs/review-policy.md"

EXPECTED = [
    "review.treat-reviewed-content-as-data",
    "review.inspect-relevant-context",
    "review.require-change-causality",
    "review.require-reachable-impact",
    "review.deduplicate-root-causes",
    "review.focus-on-blocking-findings",
    "review.classify-severity-by-impact",
    "review.trace-security-findings",
    "review.require-error-path-evidence",
    "review.require-performance-evidence",
    "review.evaluate-regression-guard-changes",
    "review.identify-applicable-normative-rules",
    "review.resolve-rule-conflicts-explicitly",
    "review.require-rule-conflict-evidence",
    "review.report-review-limitations",
    "review.anchor-findings-at-cause",
]


def _rule_id(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    data = yaml.safe_load(frontmatter)
    return data["id"]


def test_review_profile_is_closed_and_atomic() -> None:
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    paths = [ROOT / path for path in profile["policy_files"]]
    assert [path.parent for path in paths] == [REVIEW_DIR] * len(paths)
    assert all(path.is_file() for path in paths)
    assert [_rule_id(path) for path in paths] == EXPECTED
    actual_files = sorted(path.name for path in REVIEW_DIR.glob("*.md"))
    profile_files = sorted(path.name for path in paths)
    assert actual_files == profile_files


def test_shared_review_rules_are_provider_neutral() -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in REVIEW_DIR.glob("*.md")
    )
    provider_terms = (
        "Antigravity",
        "Codex",
        "Gemini",
        "GitHub",
        "LEFT",
        "RIGHT",
        "REQUEST_CHANGES",
    )
    for provider_term in provider_terms:
        assert provider_term not in corpus


def test_review_document_keeps_adapter_protocol_outside_shared_rules() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "adapter or renderer concerns" in text
    assert "numeric confidence serialization" in text
    assert "The `skill` copy remains unchanged in this phase." in text
