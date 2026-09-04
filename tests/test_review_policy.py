from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agent_policy.policy_loader import load_rules, parse_policy

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/review.yml"
REVIEW_DIR = ROOT / "policy/review"
DOC = ROOT / "docs/review-policy.md"
DISPOSITION = ROOT / "docs/review-guidance-disposition.json"
ADR = ROOT / "docs/adr/0009-review-result-representation-boundary.md"

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
    "review.keep-findings-independently-addressable",
    "review.anchor-findings-at-cause",
]

FROZEN_INPUT_IDS = [
    *(f"RG-{number:02d}" for number in range(1, 10)),
    *(f"AP-{number:02d}" for number in range(1, 9)),
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
        "APPROVE",
        "REQUEST_CHANGES",
        "COMMENT",
        "analysis_status",
        "schema_version",
        "github-review-json-adapter-v1",
        "Return exactly one standard JSON object",
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


def test_review_document_keeps_representation_outside_review_authority() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "not required review-result semantics" in text
    assert "non-normative integration reference" in text
    assert (
        "not a reason to invent a repository-owned general-purpose review JSON schema"
        in text
    )
    assert (
        "does not require one JSON object, JSON-only output, or exact response-field names"
        in text
    )


def test_review_document_describes_current_self_hosted_authority_layers() -> None:
    text = DOC.read_text(encoding="utf-8")

    required = (
        "## Current review authority layers",
        "Semantic policy",
        "Provider-neutral review procedure",
        "Procedure references",
        "Empirical evaluation material",
        "Provider integration",
        "skills/pr-review/SKILL.md",
        ".review-authority/review-policy.md",
        ".agents/skills/pr-review/",
        "Sole procedural authority",
        "Evaluation evidence is non-authoritative",
        "Current consumers receive the semantic projection and generated `pr-review` procedure",
    )
    for phrase in required:
        assert phrase in text

    stale_migration_claims = (
        "belongs to the planned review procedure",
        "downstream responsibilities planned for `skills/pr-review/SKILL.md`",
        "The `skill` copy remains unchanged in this phase.",
        "It is removed or regenerated only after the shared review policy can be selected",
    )
    for phrase in stale_migration_claims:
        assert phrase not in text


def test_review_document_keeps_multiple_passes_under_single_semantic_authority() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Different analysis passes may inspect those perspectives" in text
    assert "overlapping policy authority would reintroduce ambiguity" in text
    assert "a provider-neutral method for discovering or falsifying defect candidates" in text
    assert "must not silently become universal semantic authority" in text


def test_review_representation_boundary_preserves_trust_without_adapter_identity() -> None:
    text = ADR.read_text(encoding="utf-8")
    assert "Supersedes in part: ADR-0008" in text
    assert "Review authority stops before provider serialization" in text
    assert "a provider adapter projection" in text
    assert "an adapter renderer identifier" in text
    assert "adapter-byte identity in final stability checks" in text
    assert "All other ADR-0008 trust machinery remains in force" in text
    assert "GitHub API request payload examples only" in text
    assert "not the required output format of the review procedure" in text


def test_frozen_review_guidance_has_one_complete_disposition_inventory() -> None:
    data = json.loads(DISPOSITION.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["authoritative"] is False
    assert data["source"] == "docs/review-guidance-inputs.md"

    inputs = data["inputs"]
    assert [item["id"] for item in inputs] == FROZEN_INPUT_IDS
    assert len({item["id"] for item in inputs}) == len(FROZEN_INPUT_IDS)
    assert all(item["dispositions"] for item in inputs)


def test_review_guidance_dispositions_reference_one_semantic_authority_set() -> None:
    data = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    rules = load_rules(ROOT, ["core", "security-baseline", "review"], [])
    rule_ids = {rule.id for rule in rules}
    allowed_classes = {
        "existing_authority",
        "new_semantic_rule",
        "procedure",
        "adapter",
        "explanatory",
    }
    new_semantic_authorities: set[str] = set()

    for item in data["inputs"]:
        seen: set[tuple[str, str]] = set()
        for disposition in item["dispositions"]:
            classification = disposition["class"]
            authority = disposition["authority"]
            assert classification in allowed_classes
            assert isinstance(authority, str) and authority
            assert (classification, authority) not in seen
            seen.add((classification, authority))

            if classification in {"existing_authority", "new_semantic_rule"}:
                assert authority in rule_ids
            if classification == "new_semantic_rule":
                new_semantic_authorities.add(authority)

    assert new_semantic_authorities == {"review.assess-applicable-risk-domains"}


def test_ap07_preserves_frozen_adapter_class_without_renderer_authority() -> None:
    data = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    ap07 = next(item for item in data["inputs"] if item["id"] == "AP-07")
    assert ap07["dispositions"] == [
        {"class": "procedure", "authority": "skills/pr-review/SKILL.md"},
        {
            "class": "adapter",
            "authority": "skills/pr-review/references/github-pull-request-review-api.md",
        },
    ]
    serialized = json.dumps(ap07, sort_keys=True)
    assert "github-review-json-adapter-v1" not in serialized
    assert "renderer:" not in serialized
