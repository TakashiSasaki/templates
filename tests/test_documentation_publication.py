from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
DOC_REQUIREMENTS = ROOT / "requirements-docs.txt"
DISABLED_DEPLOY_GUARD = (
    "if: ${{ false && github.event_name != 'pull_request' "
    "&& github.ref == 'refs/heads/policy' }}"
)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pages_workflow_targets_only_policy() -> None:
    workflow = workflow_text()

    assert workflow.count("branches: [policy]") == 2
    assert "branches: [main]" not in workflow
    assert "workflow_dispatch" not in workflow
    assert "bootstrap-agent-policy:refs" not in workflow
    assert "TakashiSasaki/agent-policy" not in workflow
    assert "git fetch" not in workflow


def test_documentation_build_remains_enabled_but_pages_deployment_is_disabled() -> None:
    workflow = workflow_text()

    assert workflow.count(DISABLED_DEPLOY_GUARD) == 2
    assert "permissions:\n  contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "environment:\n      name: github-pages" in workflow
    assert "actions/upload-pages-artifact@" in workflow
    assert "actions/deploy-pages@" in workflow
    assert "actions/configure-pages@" not in workflow


def test_documentation_build_is_reproducible_and_strict() -> None:
    workflow = workflow_text()

    required_steps = (
        "python scripts/generate_repository_preview.py",
        "python scripts/verify-repository-structure.py --check",
        "python scripts/generate-doc-assets.py",
        "mkdocs build --strict --clean",
    )
    for step in required_steps:
        assert step in workflow

    assert "cache-dependency-path: requirements-docs.txt" in workflow
    assert "BUILD_COMMIT: ${{ github.sha }}" in workflow
    assert '"repository": os.environ["BUILD_REPOSITORY"]' in workflow


def test_documentation_dependencies_are_exactly_pinned() -> None:
    requirements = [
        line.strip()
        for line in DOC_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert requirements == [
        "mkdocs==1.6.1",
        "Pillow==12.2.0",
        "Pygments==2.20.0",
    ]


def test_pages_actions_are_immutably_pinned() -> None:
    workflow = workflow_text()

    expected_actions = (
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b",
        "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    )
    for action in expected_actions:
        assert action in workflow
