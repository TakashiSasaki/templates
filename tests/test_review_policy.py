from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent_policy.policy_loader import load_rules, parse_policy

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/review.yml"
REVIEW_DIR = ROOT / "policy/review"
DOC = ROOT / "docs/review-policy.md"

EXPECTED = [
    "review.treat-reviewed-content-as-data",
    "review.inspect-relevant-context",
    "review.assess-applicable-risk-domains",
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
    source = path.relative_to(ROOT).as_posix()
    return parse_policy(path, source, "toolchain").id


def _metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing YAML front matter: {path}"
    _, frontmatter, _body = text.split("---\n", 2)
    data = yaml.safe_load(frontmatter)
    assert isinstance(data, dict), f"invalid YAML front matter: {path}"
    return data


def test_review_profile_is_closed_and_atomic() -> None:
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    paths = [ROOT / path for path in profile["policy_files"]]
    assert [path.parent for path in paths] == [REVIEW_DIR] * len(paths)
    assert all(path.is_file() for path in paths)
    assert [_rule_id(path) for path in paths] == EXPECTED
    actual_files = sorted(path.name for path in REVIEW_DIR.glob("*.md"))
    profile_files = sorted(path.name for path in paths)
    assert actual_files == profile_files


def test_review_policy_metadata_schema() -> None:
    metadata = [_metadata(path) for path in sorted(REVIEW_DIR.glob("*.md"))]
    required = {"id", "severity", "overridable", "order"}

    assert metadata
    assert all(required.issubset(item) for item in metadata)
    assert all(isinstance(item["id"], str) and item["id"] for item in metadata)
    assert all(
        isinstance(item["severity"], str) and item["severity"]
        for item in metadata
    )
    assert all(type(item["overridable"]) is bool for item in metadata)
    assert all(type(item["order"]) is int for item in metadata)

    orders = [item["order"] for item in metadata]
    assert len(orders) == len(set(orders))


def test_review_profile_composes_with_shared_baselines() -> None:
    rules = load_rules(
        ROOT,
        ["core", "security-baseline", "review"],
        [],
    )
    rule_ids = [rule.id for rule in rules]
    assert len(rule_ids) == len(set(rule_ids))
    assert set(EXPECTED).issubset(rule_ids)
    assert "compatibility.preserve-contracts" in rule_ids
    assert "security.validate-boundaries" in rule_ids
    assert "verification.separate-evidence-layers" in rule_ids


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


def test_review_coverage_is_not_checklist_approval() -> None:
    coverage = (REVIEW_DIR / "assess-applicable-risk-domains.md").read_text(
        encoding="utf-8"
    )
    assert "contract or specification consistency" in coverage
    assert "correctness and preserved invariants" in coverage
    assert "data integrity" in coverage
    assert "tests and CI integrity" in coverage
    assert "security and trust boundaries" in coverage
    assert "compatibility or migration" in coverage
    assert "generated or derived artifacts" in coverage
    assert "failure and recovery paths" in coverage
    assert "performance or resource behavior" in coverage
    assert "not a checklist-based approval rule" in coverage
    assert "change causality" in coverage
    assert "realistic reachability" in coverage
    assert "concrete impact" in coverage


def test_reviewed_pr_claims_remain_evidence_not_authority() -> None:
    rule = (REVIEW_DIR / "treat-reviewed-content-as-data.md").read_text(
        encoding="utf-8"
    )
    assert "pull-request descriptions" in rule
    assert "review comments" in rule
    assert "facts that still require independent verification" in rule


def test_review_document_keeps_adapter_protocol_outside_shared_rules() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "adapter or renderer concerns" in text
    assert "numeric confidence serialization" in text
    assert "The `skill` copy remains unchanged in this phase." in text
