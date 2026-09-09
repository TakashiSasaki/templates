from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGED_RULE = ROOT / "policy" / "pull-request" / "staged-ci-and-preflight.md"
EXACT_HEAD_RULE = ROOT / "policy" / "pull-request" / "exact-head-ci-evidence.md"
DEFER_RULE = ROOT / "policy" / "pull-request" / "defer-revision-bound-qualification.md"
DOCS = ROOT / "docs" / "staged-ci.md"
MKDOCS = ROOT / "mkdocs.yml"


def test_staged_ci_rule_defines_distinct_validation_roles() -> None:
    text = STAGED_RULE.read_text(encoding="utf-8").lower()
    for fragment in (
        "ci preflight",
        "core validation",
        "conditional integration",
        "full qualification",
        "stage names describe validation role and execution cost, not importance",
        "stage**, **applicability**, and **result** as separate dimensions",
    ):
        assert fragment in text


def test_staged_ci_does_not_weaken_exact_head_or_applicability_rules() -> None:
    staged = STAGED_RULE.read_text(encoding="utf-8").lower()
    exact = EXACT_HEAD_RULE.read_text(encoding="utf-8").lower()
    for fragment in (
        "passing ci preflight does not establish",
        "not-applicable",
        "uncertain applicability must fail closed",
        "must not suppress repository-required automatic checks",
    ):
        assert fragment in staged
    assert "passing ci preflight" in exact
    assert "every check that current repository authority requires" in exact


def test_provisional_candidates_can_use_early_stages_without_full_qualification() -> None:
    text = DEFER_RULE.read_text(encoding="utf-8").lower()
    assert "ci preflight, core validation" in text
    assert "conditional integration" in text
    assert "full qualification should normally remain bound" in text
    assert "earlier ci stages" in text


def test_staged_ci_documentation_is_reader_visible_and_rejects_false_preflight() -> None:
    docs = DOCS.read_text(encoding="utf-8").lower()
    nav = MKDOCS.read_text(encoding="utf-8")
    assert "stage 0 — ci preflight" in docs
    assert "preflight passed` as shorthand for `ci passed" in docs
    assert "calling a high-cost core or integration suite a preflight" in docs
    assert "Staged CI and preflight: staged-ci.md" in nav


def test_staged_ci_distinguishes_construction_and_qualification_candidates() -> None:
    staged = STAGED_RULE.read_text(encoding="utf-8").lower()
    defer = DEFER_RULE.read_text(encoding="utf-8").lower()
    docs = DOCS.read_text(encoding="utf-8").lower()

    for target in (staged, docs):
        assert "construction candidate" in target
        assert "qualification candidate" in target
        assert "l0/l1 green ≠ merge-ready" in target
        assert (
            "do not stall dependency-safe construction" in target
            or "do not block construction on heavy ci" in target
        )
        assert (
            "intermediate heads do not each require full qualification" in target
            or "stack-tip qualification" in target
        )

    assert "construction candidate" in defer
    assert "qualification candidate" in defer


def test_ci_applicability_classifier_contract_is_canonical() -> None:
    exact = EXACT_HEAD_RULE.read_text(encoding="utf-8").lower()
    docs = DOCS.read_text(encoding="utf-8").lower()

    for target in (exact, docs):
        assert "classifier contract" in target
        assert "base-authoritative" in target
        assert "deterministic" in target
        assert "fail-closed" in target
        assert "self-exempt" in target
        assert "explicit escalation" in target
        for risk_class in (
            "documentation-only",
            "tests-only",
            "content",
            "runtime-sensitive",
            "browser-sensitive",
            "publication-sensitive",
            "cross-authority-sensitive",
            "distribution-sensitive",
            "ci-authority-sensitive",
            "unknown",
        ):
            assert risk_class in target


