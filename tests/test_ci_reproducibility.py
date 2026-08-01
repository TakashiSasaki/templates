from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
CI_REQUIREMENTS = ROOT / "requirements-ci.txt"
CI_LOCK = ROOT / "requirements-ci.lock"


def non_comment_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_policy_ci_uses_the_validated_runner_and_python_release() -> None:
    workflow = workflow_text()

    assert "runs-on: ubuntu-24.04" in workflow
    assert "runs-on: ubuntu-latest" not in workflow
    assert 'python-version: "3.12.13"' in workflow
    assert 'python-version: "3.12"' not in workflow


def test_policy_ci_installs_only_the_locked_dependency_graph() -> None:
    workflow = workflow_text()

    assert "cache-dependency-path: requirements-ci.lock" in workflow
    assert "-r requirements-ci.lock" in workflow
    assert "cache-dependency-path: pyproject.toml" not in workflow
    assert "-e '.[dev]'" not in workflow
    assert "--no-deps --no-build-isolation -e ." in workflow
    assert "python -m pip check" in workflow


def test_ci_dependency_inputs_are_exactly_pinned() -> None:
    assert non_comment_lines(CI_REQUIREMENTS) == [
        "editables==0.6",
        "hatchling==1.31.0",
        "Jinja2==3.1.6",
        "jsonschema==4.26.0",
        "Pygments==2.20.0",
        "pytest==8.4.2",
        "PyYAML==6.0.3",
        "ruff==0.15.22",
    ]


def test_ci_dependency_graph_is_fully_locked() -> None:
    locked = non_comment_lines(CI_LOCK)

    assert locked == [
        "attrs==26.1.0",
        "editables==0.6",
        "hatchling==1.31.0",
        "iniconfig==2.3.0",
        "Jinja2==3.1.6",
        "jsonschema==4.26.0",
        "jsonschema-specifications==2025.9.1",
        "MarkupSafe==3.0.3",
        "packaging==26.2",
        "pathspec==1.1.1",
        "pluggy==1.6.0",
        "Pygments==2.20.0",
        "pytest==8.4.2",
        "PyYAML==6.0.3",
        "referencing==0.37.0",
        "rpds-py==2026.6.3",
        "ruff==0.15.22",
        "trove-classifiers==2026.6.1.19",
        "typing_extensions==4.16.0",
    ]
    assert all(line.count("==") == 1 for line in locked)
    assert set(non_comment_lines(CI_REQUIREMENTS)).issubset(locked)


def test_policy_ci_actions_are_immutably_pinned() -> None:
    workflow = workflow_text()

    expected_actions = (
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
    )
    for action in expected_actions:
        assert action in workflow
