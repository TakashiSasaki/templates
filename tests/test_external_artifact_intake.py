from pathlib import Path

from agent_policy.commands import check, init, validate
from agent_policy.policy_loader import load_rules
from agent_policy.renderer import render_skill

CORE_ADDITIONS = {
    "changes.preserve-acceptance-baseline",
    "decisions.escalate-semantic-ambiguity",
    "verification.separate-evidence-layers",
    "safety.limit-rollback-to-owned-changes",
}

ARTIFACT_RULES = {
    "artifacts.distinguish-provenance-integrity",
    "artifacts.validate-before-use",
    "artifacts.apply-declared-intent-only",
    "artifacts.separate-staging-adaptation-activation",
    "artifacts.isolate-transport-material",
    "artifacts.minimize-dependency-closure",
}

GENERATED_SKILLS = [
    "validate-agent-policy",
    "intake-validated-artifact",
    "audit-frozen-change",
]


def test_core_profile_adds_universal_rules_without_artifact_profile(tmp_path: Path) -> None:
    rules = load_rules(tmp_path, ["core"], [])
    ids = [rule.id for rule in rules]

    assert CORE_ADDITIONS <= set(ids)
    assert ARTIFACT_RULES.isdisjoint(ids)
    assert len(ids) == len(set(ids))
    assert [(rule.order, rule.id) for rule in rules] == sorted(
        (rule.order, rule.id) for rule in rules
    )


def test_external_artifact_profile_is_explicit_and_deterministic(tmp_path: Path) -> None:
    rules = load_rules(tmp_path, ["core", "external-artifact-intake"], [])
    ids = [rule.id for rule in rules]

    assert CORE_ADDITIONS <= set(ids)
    assert ARTIFACT_RULES <= set(ids)
    assert len(ids) == len(set(ids))
    assert [(rule.order, rule.id) for rule in rules] == sorted(
        (rule.order, rule.id) for rule in rules
    )


def test_artifact_operational_skills_render_with_required_boundaries() -> None:
    intake = render_skill("intake-validated-artifact")["SKILL.md"]
    audit = render_skill("audit-frozen-change")["SKILL.md"]

    assert "agent-policy-generated: true" in intake
    assert "name: intake-validated-artifact" in intake
    assert "temporary storage outside the repository" in intake
    assert "Apply only entries whose declared intent authorizes" in intake
    assert "Do not publish, activate, deploy, or finalize" in intake
    assert "scan3" not in intake

    assert "agent-policy-generated: true" in audit
    assert "name: audit-frozen-change" in audit
    assert "Do not retroactively introduce a new completion gate" in audit
    assert "Repository-local checks" not in audit
    assert "repository-local checks" in audit
    assert "Completion or stop decision" in audit
    assert "scan3" not in audit


def test_init_round_trip_with_artifact_profile_and_skills(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    diagnostics = init.run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "external-artifact-intake"],
        enabled_skills=GENERATED_SKILLS,
    )

    assert diagnostics == []
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "rule ID: `changes.preserve-acceptance-baseline`" in agents
    assert "rule ID: `artifacts.validate-before-use`" in agents
    assert "`.agents/skills/intake-validated-artifact/SKILL.md`" in agents
    assert "`.agents/skills/audit-frozen-change/SKILL.md`" in agents

    for skill in GENERATED_SKILLS:
        assert (tmp_path / f".agents/skills/{skill}/SKILL.md").is_file()

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []
