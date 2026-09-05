from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EMPIRICAL = ROOT / "review-evals" / "cases" / "empirical"
MAINTAINER_DOC = ROOT / "docs" / "policy-maintainer-workflow.md"
CONFIG = ROOT / ".agent-policy.yml"
AUTHORITY = ROOT / "repository-policy" / "authority-boundary.md"
RELEASE_TRUST = ROOT / "repository-policy" / "release-trust.md"

EXPECTED_CASES = {
    "pr722-stale-async-context-completion": {
        "concurrency-and-temporal-consistency",
        "state-mutation-and-recovery",
        "consumer-and-execution-paths",
    },
    "pr722-incomplete-relation-validation": {
        "consumer-and-execution-paths",
        "namespace-and-indirection",
    },
    "pr722-incomplete-provenance-record-validation": {
        "build-provenance-and-ci",
        "identity-and-authority",
        "consumer-and-execution-paths",
    },
    "pr722-namespace-role-inconsistency": {
        "identity-and-authority",
        "namespace-and-indirection",
        "consumer-and-execution-paths",
    },
    "pr722-container-boundary-overflow": {
        "resource-behavior",
        "consumer-and-execution-paths",
    },
    "pr722-same-document-invalid-state-transition": {
        "state-mutation-and-recovery",
        "consumer-and-execution-paths",
    },
}


def _load_case(case_id: str) -> dict[str, object]:
    value = json.loads((EMPIRICAL / f"{case_id}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_playground_review_findings_are_preserved_as_general_empirical_cases() -> None:
    for case_id, expected_domains in EXPECTED_CASES.items():
        case = _load_case(case_id)
        assert case["id"] == case_id
        assert case["kind"] == "empirical"
        assert case["authority"] == "non-authoritative-evaluation"
        assert set(case["risk_domains"]) == expected_domains
        assert case["expected_review"]["disposition"] == "blocking-finding"
        provenance = case["provenance"]
        assert provenance["repository"] == "TakashiSasaki/templates"
        assert provenance["pull_request"] == 722
        assert provenance["head_binding"] == "exact"
        assert len(provenance["reviewed_head"]) == 40


def test_empirical_cases_exercise_the_new_convergence_reasoning() -> None:
    cases = [_load_case(case_id) for case_id in EXPECTED_CASES]
    text = json.dumps(cases, sort_keys=True)
    for mechanism in (
        "stale continuation",
        "required relation is complete",
        "complete record",
        "cross-field",
        "effective desktop reader container",
        "same-document transition",
    ):
        assert mechanism in text
    assert "testing.require-adversarial-invariant-coverage" in text


def test_maintainer_guidance_preserves_non_self_authorizing_adoption() -> None:
    text = MAINTAINER_DOC.read_text(encoding="utf-8").lower()
    for phrase in (
        "not a second semantic policy authority",
        "shared application-neutral policy",
        "policy-provider-specific maintenance requirements",
        "full immutable commit sha",
        "must not become the authority that declares that same change acceptable",
        "do not directly edit generated maintainer outputs",
        "focused diagnostic validation",
        "revision-bound qualification",
        "separate-promotion trust boundary",
        "separate reviewed maintenance change",
        "circular trust chain",
    ):
        assert phrase in text


def test_policy_repository_maintainers_consume_shared_and_local_authority_layers() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    coding = config["contexts"]["coding"]
    assert coding["profiles"] == ["core", "security-baseline", "pull-request"]
    project_files = coding["project_policy"]["files"]
    assert "repository-policy/maintainer-validation.md" in project_files

    authority = AUTHORITY.read_text(encoding="utf-8").lower()
    assert "keep shared policy semantics in the shared `policy/` corpus" in authority
    assert "keep repository-maintainer rules in `repository-policy/`" in authority

    release = RELEASE_TRUST.read_text(encoding="utf-8").lower()
    assert "frozen reviewed candidate followed by a separate promotion change" in release
