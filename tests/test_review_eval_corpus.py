from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from agent_policy.policy_loader import load_rules

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "review-evals"
SCHEMA_PATH = EVAL_ROOT / "review-eval-case.schema.json"
CASE_ROOT = EVAL_ROOT / "cases"
EXPECTED_RISK_DOMAINS = {
    "identity-and-authority",
    "namespace-and-indirection",
    "state-mutation-and-recovery",
    "concurrency-and-temporal-consistency",
    "privileged-execution",
    "persistence-and-integrity",
    "external-interaction",
    "resource-behavior",
    "build-provenance-and-ci",
    "consumer-and-execution-paths",
}


def load_cases() -> list[tuple[Path, dict[str, object]]]:
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(CASE_ROOT.rglob("*.json"))
    ]


def test_review_eval_schema_and_cases_are_valid() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    cases = load_cases()

    assert cases
    for path, case in cases:
        errors = sorted(validator.iter_errors(case), key=lambda item: list(item.path))
        assert not errors, f"{path}: {[error.message for error in errors]}"
        assert path.stem == case["id"]


def test_review_eval_schema_binds_empirical_head_identity() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    exact = next(
        case
        for _, case in load_cases()
        if case["kind"] == "empirical"
        and case["provenance"]["head_binding"] == "exact"  # type: ignore[index]
    )

    exact_with_null_head = copy.deepcopy(exact)
    exact_with_null_head["provenance"]["reviewed_head"] = None  # type: ignore[index]
    assert list(validator.iter_errors(exact_with_null_head))

    exact_without_head = copy.deepcopy(exact)
    exact_without_head["provenance"].pop("reviewed_head")  # type: ignore[union-attr]
    assert list(validator.iter_errors(exact_without_head))

    unbound_with_exact_head = copy.deepcopy(exact)
    unbound_with_exact_head["provenance"]["head_binding"] = "not-established"  # type: ignore[index]
    assert list(validator.iter_errors(unbound_with_exact_head))

    valid_unbound = copy.deepcopy(exact)
    valid_unbound["provenance"]["head_binding"] = "not-established"  # type: ignore[index]
    valid_unbound["provenance"]["reviewed_head"] = None  # type: ignore[index]
    assert not list(validator.iter_errors(valid_unbound))


def test_review_eval_case_ids_are_unique_and_non_authoritative() -> None:
    cases = load_cases()
    ids = [case["id"] for _, case in cases]

    assert len(ids) == len(set(ids))
    assert all(case["authority"] == "non-authoritative-evaluation" for _, case in cases)

    readme = (EVAL_ROOT / "README.md").read_text(encoding="utf-8")
    assert "non-authoritative empirical and synthetic evaluation material" in readme
    assert "does not define semantic policy" in readme
    assert "Normal CI does **not** invoke a language model" in readme


def test_review_eval_corpus_covers_all_procedure_risk_domains() -> None:
    cases = load_cases()
    covered = {
        domain
        for _, case in cases
        for domain in case["risk_domains"]  # type: ignore[union-attr]
    }
    assert covered == EXPECTED_RISK_DOMAINS


def test_review_eval_corpus_has_empirical_transposition_and_negative_controls() -> None:
    cases = load_cases()
    kinds = [case["kind"] for _, case in cases]
    dispositions = [
        case["expected_review"]["disposition"]  # type: ignore[index]
        for _, case in cases
    ]

    assert kinds.count("empirical") >= 3
    assert kinds.count("semantic-transposition") >= 5
    assert kinds.count("control") >= 2
    assert "blocking-finding" in dispositions
    assert "completed-no-blocking-finding" in dispositions
    assert "incomplete-review" in dispositions


def test_empirical_review_eval_cases_have_identity_bound_provenance_when_available() -> None:
    for path, case in load_cases():
        if case["kind"] != "empirical":
            assert "provenance" not in case
            continue

        provenance = case["provenance"]  # type: ignore[assignment]
        assert provenance["repository"] == "TakashiSasaki/templates"  # type: ignore[index]
        assert provenance["pull_request"] > 0  # type: ignore[index,operator]
        source_id = provenance["source_id"]  # type: ignore[index]
        assert source_id.startswith(("PRR_", "PRRC_"))
        if provenance["head_binding"] == "exact":  # type: ignore[index]
            assert re.fullmatch(r"[0-9a-f]{40}", provenance["reviewed_head"])  # type: ignore[index,arg-type]
        else:
            assert provenance["head_binding"] == "not-established"  # type: ignore[index]
            assert provenance["reviewed_head"] is None  # type: ignore[index]
        assert path.parts[-2] == "empirical"


def test_review_eval_required_rule_ids_resolve_to_current_canonical_policy() -> None:
    rule_ids = {
        rule.id
        for rule in load_rules(
            ROOT,
            ["core", "security-baseline", "review", "pull-request"],
            [],
        )
    }
    referenced = {
        invariant["rule_id"]
        for _, case in load_cases()
        for invariant in case["required_invariants"]  # type: ignore[union-attr]
    }

    assert referenced <= rule_ids


def test_non_empirical_review_eval_cases_remain_technology_neutral() -> None:
    forbidden_terms = (
        "python",
        "javascript",
        "rust",
        "github",
        "posix",
        "windows",
        "os.replace",
        "path.resolve",
        "symlink",
    )

    for path, case in load_cases():
        if case["kind"] == "empirical":
            continue
        text = json.dumps(case, ensure_ascii=False).casefold()
        for term in forbidden_terms:
            pattern = rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])"
            assert re.search(pattern, text) is None, f"{path}: technology term {term}"
