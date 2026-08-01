from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_BOOTSTRAP_DOCS = (
    "README.md",
    "docs/index.md",
    "docs/getting-started.md",
    "docs/bootstrap.md",
    "docs/bootstrap-model.md",
    "docs/adoption.md",
    "docs/architecture.md",
    "docs/repository-structure.md",
    "docs/adr/0002-repository-adoption.md",
    "docs/adr/0004-integrated-bootstrap-skill.md",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def stable_toolchain() -> dict[str, str]:
    release = json.loads((ROOT / "release/toolchain.json").read_text(encoding="utf-8"))
    toolchain = release["toolchain"]
    assert isinstance(toolchain, dict)
    return toolchain


def test_bootstrap_package_is_integrated_and_pinned() -> None:
    skill_root = ROOT / "skills/bootstrap-agent-policy"
    expected = {
        "README.md",
        "SKILL.md",
        "bootstrap-manifest.yml",
        "scripts/bootstrap.py",
        "scripts/install.py",
        "scripts/uninstall.py",
    }
    actual = {
        path.relative_to(skill_root).as_posix()
        for path in skill_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    assert actual == expected

    manifest = json.loads((skill_root / "bootstrap-manifest.yml").read_text())
    assert manifest["toolchain"] == stable_toolchain()
    assert "finalize" not in json.dumps(manifest["routes"])


def test_active_documentation_uses_integrated_skill_layout() -> None:
    for relative in ACTIVE_BOOTSTRAP_DOCS:
        content = read(relative)
        assert "skills/bootstrap-agent-policy" in content, relative
        assert "--branch bootstrap-agent-policy" not in content, relative
        assert "-b bootstrap-agent-policy" not in content, relative
        assert "TakashiSasaki/agent-policy.git" not in content, relative
        assert "directly cloneable onboarding skill" not in content, relative


def test_repository_structure_and_preview_are_policy_only() -> None:
    structure = read("docs/repository-structure.md")
    assert "BEGIN VERIFIED TREE: policy" in structure
    assert "END VERIFIED TREE: policy" in structure
    assert "BEGIN VERIFIED TREE: main" not in structure
    assert "BEGIN VERIFIED TREE: bootstrap-agent-policy" not in structure

    generator = read("scripts/generate_repository_preview.py")
    verifier = read("scripts/verify-repository-structure.py")
    for content in (generator, verifier):
        assert 'BRANCH_REFS = {"policy": "HEAD"}' in content
        assert "REMOTE_BOOTSTRAP_REF" not in content
    assert 'REPOSITORY = "TakashiSasaki/templates"' in generator


def test_adr_records_layout_supersession() -> None:
    original = read("docs/adr/0001-unrelated-bootstrap-history.md")
    integrated = read("docs/adr/0004-integrated-bootstrap-skill.md")
    navigation = read("mkdocs.yml")

    assert "Status: Superseded" in original
    assert "Superseded by: ADR-0004" in original
    assert "Status: Accepted" in integrated
    assert "Supersedes: ADR-0001" in integrated
    assert "adr/0004-integrated-bootstrap-skill.md" in navigation


def test_policy_ci_validates_bootstrap_scripts() -> None:
    workflow = read(".github/workflows/ci.yml")
    assert "ruff check src tests scripts skills/bootstrap-agent-policy/scripts" in workflow
    assert "skills/bootstrap-agent-policy/scripts" in workflow


def test_migration_status_marks_bootstrap_consolidation_complete() -> None:
    readme = read("README.md")
    migration = read("docs/migration-from-agent-policy.md")
    assert "consolidation of the bootstrap trust seed" in readme
    assert "integrated the bootstrap trust seed" in migration
    assert "Consolidate the bootstrap skill" not in migration
