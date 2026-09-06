from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/orchestrate-repository-change"


def test_work_ledger_is_discoverable_and_distributed_without_runtime_artifact():
    rendered = render_skill("orchestrate-repository-change")
    source = (SKILL / "references/work-ledger.md").read_text()
    installed = rendered["references/work-ledger.md"]

    assert "references/work-ledger.md" in rendered["SKILL.md"]
    assert "../../pr-merge-gate/references/review-finding-ledger.md" in source
    assert "../../pr-merge-gate/references/review-feedback-disposition.md" in source
    assert "(review-finding-ledger.md)" in installed
    assert "(review-feedback-disposition.md)" in installed
    assert "../../pr-merge-gate/references/" not in installed
    assert not (ROOT / ".work-ledger.json").exists()


def test_work_ledger_preserves_storage_and_acceptance_boundaries():
    text = (SKILL / "references/work-ledger.md").read_text().lower()
    for required in (
        "repository-associated, but not repository-tracked by default",
        "canonical provider facts; ledger entries are observations",
        "not a new source of semantic acceptance policy",
        "neither replaces those artifacts nor establishes product acceptance",
        "do not create a repository file solely",
        "not a mandatory json/yaml artifact",
        "do not duplicate disposition, repair reasoning",
        "review-finding-ledger.md",
        "next safe action",
        "completion / handoff boundary",
        "exact-head ci/review evidence for the old sha cannot qualify the new sha",
        "do not mechanically discard all state",
        "do not append a transcript",
        "persist the preflight checkpoint first",
        "stop without polling, a post-request checkpoint write",
    ):
        assert required in text
