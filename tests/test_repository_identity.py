from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
MKDOCS = ROOT / "mkdocs.yml"
PWA_SCRIPT = ROOT / "docs/assets/javascripts/pwa.js"
WORKFLOW = ROOT / ".github/workflows/ci.yml"
REPOSITORY_IDENTITY = re.compile(r"TakashiSasaki/[A-Za-z0-9_.-]+")
CURRENT_REPOSITORY = "TakashiSasaki/templates"
TEXT_ROOTS = (
    ROOT / ".github",
    ROOT / "docs",
    ROOT / "policy",
    ROOT / "profiles",
    ROOT / "repository-policy",
    ROOT / "schemas",
    ROOT / "scripts",
    ROOT / "skills",
    ROOT / "src",
    ROOT / "templates",
    ROOT / "tests",
)
TOP_LEVEL_TEXT = (
    ROOT / ".agent-policy.yml",
    ROOT / "AGENTS.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "action.yml",
    ROOT / "mkdocs.yml",
    ROOT / "pyproject.toml",
)


def test_readme_identifies_policy_branch_and_application_neutral_scope() -> None:
    readme = README.read_text(encoding="utf-8")

    assert CURRENT_REPOSITORY in readme
    assert "branch `policy`" in readme
    assert "application-type-independent" in readme
    assert "The repository has two unrelated long-lived branches" not in readme


def test_maintained_text_uses_only_current_repository_identity() -> None:
    files = list(TOP_LEVEL_TEXT)
    for root in TEXT_ROOTS:
        files.extend(path for path in root.rglob("*") if path.is_file())

    checked = 0
    for path in sorted(set(files)):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        checked += 1
        identities = set(REPOSITORY_IDENTITY.findall(content))
        assert identities <= {CURRENT_REPOSITORY}, path.relative_to(ROOT).as_posix()
    assert checked > 0


def test_documentation_metadata_points_to_templates_policy() -> None:
    configuration = MKDOCS.read_text(encoding="utf-8")
    pwa_script = PWA_SCRIPT.read_text(encoding="utf-8")

    assert "repo_url: https://github.com/TakashiSasaki/templates" in configuration
    assert "repo_name: TakashiSasaki/templates" in configuration
    assert "edit_uri: edit/policy/docs/" in configuration
    assert "edit/main/docs/" not in configuration
    assert "https://github.com/TakashiSasaki/templates/commit/${info.commit}" in pwa_script


def test_policy_ci_is_branch_portable_and_does_not_target_main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Policy CI" in workflow
    assert "on:\n  push:\n  pull_request:\n" in workflow
    assert "branches: [main]" not in workflow
    assert "- main" not in workflow
    assert "ruff check src tests scripts" in workflow
    assert "pytest" in workflow
    assert "python -m compileall -q src scripts" in workflow
