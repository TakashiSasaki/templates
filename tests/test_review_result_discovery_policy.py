from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "policy" / "pull-request" / "review-result-discovery.md"
PROFILE = ROOT / "profiles" / "pull-request.yml"
CLOSURE = ROOT / "policy" / "pull-request" / "review-thread-closure.md"
REACQUISITION = (
    ROOT
    / "policy"
    / "pull-request"
    / "review-reacquisition-after-disposition.md"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_review_result_discovery_requires_cross_surface_observation() -> None:
    text = _text(RULE)
    for phrase in (
        "applicable provider-supported review-result surfaces",
        "submitted review bodies",
        "ordinary pull-request or issue comments",
        "inline review comments and resolvable review threads",
        "reconstruct the logical result",
        "absence of findings on any single provider surface",
        (
            "material actionable finding discovered on any applicable "
            "review-result surface"
        ),
    ):
        assert phrase in text


def test_reactions_are_not_implicitly_completion_evidence() -> None:
    text = _text(RULE)
    for phrase in (
        "reactions and similar provider signals",
        (
            "only when the applicable workflow, review procedure, or provider "
            "contract establishes their meaning"
        ),
        "uninterpreted provider state",
        "do not interpret an acknowledgement or attention signal as review completion",
    ):
        assert phrase in text


def test_discovery_failure_is_fail_closed() -> None:
    text = _text(RULE)
    assert "cannot inspect a provider surface" in text
    assert "keep any affected completion or no-findings conclusion fail-closed" in text


def test_pull_request_profile_selects_discovery_rule() -> None:
    assert "policy/pull-request/review-result-discovery.md" in _text(PROFILE)


def test_existing_finding_rules_delegate_to_cross_surface_discovery() -> None:
    assert "cross-surface review-result discovery rule" in _text(CLOSURE)
    assert "cross-surface review-result discovery rule" in _text(REACQUISITION)
