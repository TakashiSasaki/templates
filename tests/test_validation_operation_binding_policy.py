from __future__ import annotations

from pathlib import Path

import yaml

from agent_policy.policy_loader import load_rules, parse_policy

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "policy/core/validation-operation-binding.md"
CORE_PROFILE = ROOT / "profiles/core.yml"


def test_core_profile_composes_validation_operation_binding() -> None:
    profile = yaml.safe_load(CORE_PROFILE.read_text(encoding="utf-8"))
    paths = profile["policy_files"]

    rule_path = "policy/core/validation-operation-binding.md"
    assert rule_path in paths
    assert paths.index("policy/core/destructive-actions.md") < paths.index(rule_path)
    assert paths.index(rule_path) < paths.index("policy/core/transaction-ownership.md")

    rules = load_rules(ROOT, ["core"], [])
    assert "safety.bind-validated-state-to-operation" in {rule.id for rule in rules}


def test_validation_operation_binding_is_mandatory_shared_semantics() -> None:
    rule = parse_policy(
        RULE,
        RULE.relative_to(ROOT).as_posix(),
        "toolchain",
    )

    assert rule.id == "safety.bind-validated-state-to-operation"
    assert rule.severity == "mandatory"
    assert rule.overridable is False

    text = RULE.read_text(encoding="utf-8")
    for requirement in (
        "same effective target",
        "normalization",
        "indirection",
        "aliases",
        "redirects",
        "rebinding",
        "concurrent mutation",
        "protected commit or use boundary",
        "Fail closed",
    ):
        assert requirement in text


def test_validation_operation_binding_remains_technology_neutral() -> None:
    text = RULE.read_text(encoding="utf-8")

    technology_specific_terms = (
        "Python",
        "JavaScript",
        "Rust",
        "GitHub",
        "POSIX",
        "Windows",
        "os.replace",
        "Path.resolve",
        "symlink",
    )
    for term in technology_specific_terms:
        assert term not in text
