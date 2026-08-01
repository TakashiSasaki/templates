from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
DOC_REQUIREMENTS = ROOT / "requirements-docs.txt"
DOC_LOCK = ROOT / "requirements-docs.lock"
DISABLED_DEPLOY_GUARD = (
    "if: ${{ false && github.event_name != 'pull_request' "
    "&& github.ref == 'refs/heads/policy' }}"
)


def non_comment_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


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


def test_documentation_build_uses_the_validated_runner_release() -> None:
    workflow = workflow_text()

    assert workflow.count("runs-on: ubuntu-24.04") == 2
    assert "runs-on: ubuntu-latest" not in workflow


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

    assert "cache-dependency-path: requirements-docs.lock" in workflow
    assert "-r requirements-docs.lock" in workflow
    assert "cache-dependency-path: requirements-docs.txt" not in workflow
    assert "-r requirements-docs.txt" not in workflow
    assert "BUILD_COMMIT: ${{ github.sha }}" in workflow
    assert '"repository": os.environ["BUILD_REPOSITORY"]' in workflow


def test_documentation_dependency_inputs_are_exactly_pinned() -> None:
    assert non_comment_lines(DOC_REQUIREMENTS) == [
        "mkdocs==1.6.1",
        "Pillow==12.2.0",
        "Pygments==2.20.0",
    ]


def test_documentation_dependency_graph_is_fully_locked() -> None:
    locked = non_comment_lines(DOC_LOCK)

    assert locked == [
        "click==8.4.2",
        "ghp-import==2.1.0",
        "Jinja2==3.1.6",
        "Markdown==3.10.3",
        "MarkupSafe==3.0.3",
        "mergedeep==1.3.4",
        "mkdocs==1.6.1",
        "mkdocs-get-deps==0.2.2",
        "packaging==26.2",
        "pathspec==1.1.1",
        "Pillow==12.2.0",
        "platformdirs==4.11.0",
        "Pygments==2.20.0",
        "python-dateutil==2.9.0.post0",
        "PyYAML==6.0.3",
        "pyyaml-env-tag==1.1",
        "six==1.17.0",
        "watchdog==6.0.0",
    ]
    assert all(line.count("==") == 1 for line in locked)


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
