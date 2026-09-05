from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CORE_PROFILE = ROOT / "profiles" / "core.yml"
PULL_REQUEST_PROFILE = ROOT / "profiles" / "pull-request.yml"
ADVERSARIAL_RULE = ROOT / "policy" / "core" / "adversarial-invariant-testing.md"
REVIEW_PREFLIGHT_RULE = (
    ROOT / "policy" / "pull-request" / "review-acquisition-preflight.md"
)
SELF_HOST_CONFIG = ROOT / ".agent-policy.yml"


def _yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_review_convergence_rules_are_selected_by_shared_profiles() -> None:
    core = _yaml(CORE_PROFILE)
    pull_request = _yaml(PULL_REQUEST_PROFILE)

    assert "policy/core/adversarial-invariant-testing.md" in core["policy_files"]
    assert (
        "policy/pull-request/review-acquisition-preflight.md"
        in pull_request["policy_files"]
    )


def test_adversarial_invariant_rule_is_bounded_and_risk_triggered() -> None:
    text = _text(ADVERSARIAL_RULE)
    for phrase in (
        "structured contract",
        "asynchronous completion",
        "stale-state",
        "converse/completeness",
        "effective inner containment boundary",
        "bounded sibling",
    ):
        assert phrase in text
    assert "fixed universal matrix" in text
    assert "do not require unrelated combinations" in text
    for artifact_specific_term in ("browser", "viewport"):
        assert artifact_specific_term not in text


def test_review_acquisition_preflight_checks_identity_without_becoming_review_evidence() -> None:
    text = _text(REVIEW_PREFLIGHT_RULE)
    for phrase in (
        "current proposed head",
        "currently resolvable",
        "ordered stack membership",
        "integration-base",
        "do not invoke the reviewer",
    ):
        assert phrase in text
    assert "not completed-review evidence" in text
    assert "does not establish merge readiness" in text
    assert "fixed waiting period" in text


def test_policy_repository_self_host_selects_profiles_that_receive_the_rules() -> None:
    config = _yaml(SELF_HOST_CONFIG)
    coding = config["contexts"]["coding"]
    assert "core" in coding["profiles"]
    assert "pull-request" in coding["profiles"]

    toolchain = config["toolchain"]
    revision = toolchain["revision"]
    assert isinstance(revision, str)
    assert len(revision) == 40
    assert all(character in "0123456789abcdef" for character in revision)
