from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/pr-review/SKILL.md"
RISK_ROOT = ROOT / "skills/pr-review/references/risk-domains"
EXPECTED_PLAYBOOKS = {
    "identity-and-authority.md",
    "namespace-and-indirection.md",
    "state-mutation-and-recovery.md",
    "concurrency-and-temporal-consistency.md",
    "privileged-execution.md",
    "persistence-and-integrity.md",
    "external-interaction.md",
    "resource-behavior.md",
    "build-provenance-and-ci.md",
    "consumer-and-execution-paths.md",
}


def test_pr_review_explicitly_uses_frozen_risk_domain_references() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "references/risk-domains/index.md" in skill
    assert "from the frozen procedure bundle" in skill
    assert "provider-neutral procedure-support material" in skill
    assert "cannot add semantic requirements" in skill
    assert "cannot promote a candidate seed to a finding" in skill
    assert "Do not execute every reference mechanically as an approval checklist" in skill


def test_risk_domain_reference_inventory_and_shape_are_stable() -> None:
    actual = {path.name for path in RISK_ROOT.glob("*.md")}
    assert actual == {"index.md"} | EXPECTED_PLAYBOOKS

    index = (RISK_ROOT / "index.md").read_text(encoding="utf-8")
    for playbook in EXPECTED_PLAYBOOKS:
        assert f"`{playbook}`" in index

    required_sections = (
        "## Trigger",
        "## State and authority model",
        "## Candidate seeds",
        "## Falsification evidence",
        "## Closure",
    )
    for playbook in EXPECTED_PLAYBOOKS:
        text = (RISK_ROOT / playbook).read_text(encoding="utf-8")
        for section in required_sections:
            assert section in text
        assert "A seed is not a finding." in text
