from pathlib import Path

import pytest

from agent_policy import renderer
from agent_policy.commands import check, init

ROOT = Path(__file__).resolve().parents[1]
SKILL = "orchestrate-repository-change"


def test_installed_consumer_can_follow_finding_procedures(tmp_path):
    (tmp_path / ".git").mkdir()
    assert init.run(
        tmp_path, ".agent-policy.yml", apply=True,
        toolchain_revision="a" * 40, profiles=["core", "pull-request"],
        enabled_skills=[SKILL],
    ) == []
    installed = tmp_path / ".agents/skills" / SKILL
    assert not (tmp_path / "skills/pr-merge-gate").exists()
    assert not (tmp_path / ".agents/skills/pr-merge-gate").exists()
    for relative, source in renderer.SKILL_REFERENCE_IMPORTS[SKILL].items():
        assert (installed / relative).read_text() == (ROOT / source).read_text()
    ledger = (installed / "references/work-ledger.md").read_text()
    assert "(review-finding-ledger.md)" in ledger
    assert "(review-feedback-disposition.md)" in ledger
    for path in installed.rglob("*.md"):
        assert "skills/pr-merge-gate/references/" not in path.read_text()
    assert check.run(tmp_path, ".agent-policy.yml") == []
    # Imported material participates in the normal managed-output integrity check.
    (installed / "references/review-finding-ledger.md").write_text("tampered\n")
    assert check.run(tmp_path, ".agent-policy.yml") != []


def test_missing_canonical_import_fails_closed(monkeypatch):
    monkeypatch.setitem(renderer.SKILL_REFERENCE_IMPORTS, SKILL, {
        "references/review-finding-ledger.md": "skills/missing/reference.md",
    })
    with pytest.raises(FileNotFoundError):
        renderer.render_skill(SKILL)


def test_import_cannot_shadow_an_authored_reference(monkeypatch):
    monkeypatch.setitem(renderer.SKILL_REFERENCE_IMPORTS, SKILL, {
        "references/work-ledger.md":
            "skills/pr-merge-gate/references/review-finding-ledger.md",
    })
    with pytest.raises(ValueError, match="collides with local source"):
        renderer.render_skill(SKILL)


@pytest.mark.parametrize("requirements", [
    (
        "preserved behavior/invariants", "required acceptance criteria and evidence",
        "resolve the authoritative change-contract locator",
        "observed evidence results do not define the required acceptance baseline",
        "if that contract is unavailable",
    ),
    (
        "evidence layer (local, environment-dependent, remote ci, independent review)",
        "exact executed command or workflow/check identity", "provenance",
        "limitations and applicability conditions",
    ),
    (
        "stable repository id", "stable pr id", "repository-qualified",
        "re-resolve stable provider/repository/member ids", "rename or transfer",
        "if identity remains ambiguous, block the mutation",
    ),
    (
        "planned/in-progress/complete/deferred", "owned paths/provider objects",
        "preflight/commit-boundary observations", "a general diff is not proof of ownership",
        "do not overwrite, delete or roll back uncertain changes",
    ),
    (
        "pre-write read and reconciliation alone do not protect",
        "single writer with serialized handoff", "append immutable checkpoint comments",
        "competing successors are a conflict", "never edit a shared pointer/comment concurrently",
    ),
])
def test_distributed_recovery_procedure_preserves_required_guards(requirements):
    text = renderer.render_skill(SKILL)["references/work-ledger.md"].lower()
    for requirement in requirements:
        assert requirement in text
