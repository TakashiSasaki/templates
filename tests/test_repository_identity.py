from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
MIGRATION = ROOT / "docs/migration-from-agent-policy.md"
MKDOCS = ROOT / "mkdocs.yml"
PWA_SCRIPT = ROOT / "docs/assets/javascripts/pwa.js"
WORKFLOW = ROOT / ".github/workflows/ci.yml"
SOURCE_HEAD = "22ac788d456bf0d9904e1d23492b01296de167a1"


def test_readme_identifies_policy_branch_and_application_neutral_scope() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "TakashiSasaki/templates" in readme
    assert "branch `policy`" in readme
    assert "application-type-independent" in readme
    assert "The repository has two unrelated long-lived branches" not in readme


def test_migration_provenance_records_filtered_source_history() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "TakashiSasaki/agent-policy" in migration
    assert SOURCE_HEAD in migration
    assert "`.github/workflows` was removed from every imported revision" in migration
    assert "imported commit SHAs are not expected to equal the original SHAs" in migration


def test_documentation_metadata_points_to_templates_policy() -> None:
    configuration = MKDOCS.read_text(encoding="utf-8")
    pwa_script = PWA_SCRIPT.read_text(encoding="utf-8")

    assert "repo_url: https://github.com/TakashiSasaki/templates" in configuration
    assert "repo_name: TakashiSasaki/templates" in configuration
    assert "edit_uri: edit/policy/docs/" in configuration
    assert "edit/main/docs/" not in configuration
    assert "https://github.com/TakashiSasaki/templates/commit/${info.commit}" in pwa_script
    assert "https://github.com/TakashiSasaki/agent-policy/commit/" not in pwa_script


def test_policy_ci_is_branch_portable_and_does_not_target_legacy_main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Policy CI" in workflow
    assert "on:\n  push:\n  pull_request:\n" in workflow
    assert "branches: [main]" not in workflow
    assert "- main" not in workflow
    assert "ruff check src tests scripts" in workflow
    assert "pytest" in workflow
    assert "python -m compileall -q src scripts" in workflow
