from pathlib import Path

from agent_policy.policy_loader import load_rules

WEB_APPLICATION_RULE_IDS = [
    "interfaces.define-surface-boundaries",
    "interfaces.isolate-surface-dependencies",
    "interfaces.make-navigation-intentional",
    "interfaces.model-user-visible-states",
    "interfaces.preserve-accessible-interaction",
    "interfaces.separate-diagnostics",
    "interfaces.keep-surface-contracts-synchronized",
    "interfaces.adapt-layout-to-content",
]


def test_web_application_profile_loads_in_declared_order(tmp_path: Path) -> None:
    rules = load_rules(tmp_path, ["web-application"], [])

    assert [rule.id for rule in rules] == WEB_APPLICATION_RULE_IDS
    assert [rule.order for rule in rules] == sorted(rule.order for rule in rules)


def test_web_application_profile_composes_with_baselines(tmp_path: Path) -> None:
    rules = load_rules(
        tmp_path,
        ["core", "security-baseline", "web-application"],
        [],
    )
    rule_ids = [rule.id for rule in rules]

    assert len(rule_ids) == len(set(rule_ids))
    assert set(WEB_APPLICATION_RULE_IDS).issubset(rule_ids)
