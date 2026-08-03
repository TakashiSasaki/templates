from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
DOC_REQUIREMENTS = ROOT / "requirements-docs.txt"
DOC_LOCK = ROOT / "requirements-docs.lock"
DOC_ENVIRONMENT_VERIFIER = ROOT / "scripts/verify_docs_environment.py"
DISABLED_DEPLOY_GUARD = (
    "if: ${{ false && github.event_name != 'pull_request' "
    "&& github.ref == 'refs/heads/policy' }}"
)
ARBITRARY_EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9_.-]+===[A-Za-z0-9][A-Za-z0-9._+!-]*$"
)
PYTHON_JOB_INPUTS = (
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSAFEPATH",
    "PYTHONPLATLIBDIR",
    "PYTHONHASHSEED",
    "PYTHONUTF8",
    "PYTHONINTMAXSTRDIGITS",
    "PYTHONMALLOC",
    "PYTHONIOENCODING",
    "PYTHONTRACEMALLOC",
    "PYTHONINSPECT",
)
PIP_JOB_INPUTS = (
    "PIP_PYTHON",
    "PIP_CACHE_DIR",
    "PIP_NO_CACHE_DIR",
    "PIP_QUIET",
    "PIP_PROGRESS_BAR",
    "PIP_LOG",
    "PIP_KEYRING_PROVIDER",
    "PIP_EXISTS_ACTION",
    "PIP_USE_PEP517",
    "PIP_COMPILE",
    "PIP_ISOLATED",
    "PIP_USE_FEATURE",
    "PIP_VERBOSE",
    "PIP_DEBUG",
    "PIP_NO_INPUT",
    "PIP_DISABLE_PIP_VERSION_CHECK",
    "PIP_NO_COLOR",
    "PIP_REQUIRE_VIRTUALENV",
    "PIP_USE_DEPRECATED",
    "PIP_NO_PYTHON_VERSION_WARNING",
    "PIP_TIMEOUT",
    "PIP_DEFAULT_TIMEOUT",
    "PIP_RETRIES",
)
PIP_SANITIZED_INPUTS = (
    "PIP_REQUIREMENT",
    "PIP_CONSTRAINT",
    "PIP_BUILD_CONSTRAINT",
    "PIP_REQUIRE_HASHES",
    "PIP_DRY_RUN",
    "PIP_NO_BINARY",
    "PIP_ONLY_BINARY",
    "PIP_PLATFORM",
    "PIP_PYTHON_VERSION",
    "PIP_IMPLEMENTATION",
    "PIP_ABI",
    "PIP_UPLOADED_PRIOR_TO",
    "PIP_INDEX_URL",
    "PIP_EXTRA_INDEX_URL",
    "PIP_NO_INDEX",
    "PIP_FIND_LINKS",
    "PIP_TARGET",
    "PIP_PREFIX",
    "PIP_ROOT",
    "PIP_USER",
    "PIP_PYTHON",
    "PIP_CACHE_DIR",
    "PIP_NO_CACHE_DIR",
    "PIP_QUIET",
    "PIP_PROGRESS_BAR",
    "PIP_EDITABLE",
    "PIP_GROUP",
    "PIP_REQUIREMENTS_FROM_SCRIPT",
    "PIP_REPORT",
    "PIP_CONFIG_SETTINGS",
    "PIP_USE_PEP517",
    "PIP_COMPILE",
    "PIP_ISOLATED",
    "PIP_USE_FEATURE",
    "PIP_VERBOSE",
    "PIP_DEBUG",
    "PIP_NO_INPUT",
    "PIP_DISABLE_PIP_VERSION_CHECK",
    "PIP_NO_COLOR",
    "PIP_REQUIRE_VIRTUALENV",
    "PIP_USE_DEPRECATED",
    "PIP_NO_PYTHON_VERSION_WARNING",
    "PIP_KEYRING_PROVIDER",
    "PIP_EXISTS_ACTION",
    "PIP_IGNORE_REQUIRES_PYTHON",
    "PIP_LOG",
    "PIP_TRUSTED_HOST",
    "PIP_CERT",
    "PIP_CLIENT_CERT",
    "PIP_PROXY",
    "PIP_TIMEOUT",
    "PIP_DEFAULT_TIMEOUT",
    "PIP_RETRIES",
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


def test_documentation_build_uses_the_validated_runner_and_python_release() -> None:
    workflow = workflow_text()

    assert workflow.count("runs-on: ubuntu-24.04") == 2
    assert "runs-on: ubuntu-latest" not in workflow
    assert 'python-version: "3.12.13"' in workflow
    assert 'python-version: "3.12"' not in workflow


def test_documentation_build_clears_external_python_and_pip_inputs() -> None:
    workflow = workflow_text()

    for name in PYTHON_JOB_INPUTS:
        assert f'      {name}: ""' in workflow
    assert '      PYTHONNOUSERSITE: "1"' in workflow
    for name in PIP_JOB_INPUTS:
        assert f'      {name}: ""' in workflow
    assert "      PIP_CONFIG_FILE: /dev/null" in workflow


def test_documentation_build_uses_a_clean_locked_environment() -> None:
    workflow = workflow_text()
    workflow_unsets = " ".join(f"-u {name}" for name in PIP_SANITIZED_INPUTS)

    assert "cache-dependency-path: requirements-docs.lock" in workflow
    assert "run: python -I -m venv --clear .venv" in workflow
    assert (
        f"env {workflow_unsets} .venv/bin/python -m pip install "
        "--isolated --disable-pip-version-check --no-deps "
        "--requirement requirements-docs.lock"
    ) in workflow
    assert "run: .venv/bin/python scripts/verify_docs_environment.py" in workflow
    assert "run: .venv/bin/python -m pip check" in workflow
    assert "-r requirements-docs.lock" not in workflow
    assert "-r requirements-docs.txt" not in workflow
    assert DOC_ENVIRONMENT_VERIFIER.is_file()


def test_documentation_build_runs_every_python_tool_from_the_isolated_environment() -> None:
    workflow = workflow_text()

    required_steps = (
        ".venv/bin/python scripts/generate_repository_preview.py",
        ".venv/bin/python scripts/verify-repository-structure.py --check",
        ".venv/bin/python scripts/generate-doc-assets.py",
        ".venv/bin/python - <<'PY'",
        ".venv/bin/python -m mkdocs build --strict --clean",
    )
    for step in required_steps:
        assert step in workflow

    forbidden_steps = (
        "run: python scripts/generate_repository_preview.py",
        "run: python scripts/verify-repository-structure.py --check",
        "run: python scripts/generate-doc-assets.py",
        "run: mkdocs build --strict --clean",
    )
    for step in forbidden_steps:
        assert step not in workflow

    assert "BUILD_COMMIT: ${{ github.sha }}" in workflow
    assert '"repository": os.environ["BUILD_REPOSITORY"]' in workflow


def test_documentation_dependency_inputs_are_arbitrary_exact_reviewed_pins() -> None:
    direct = non_comment_lines(DOC_REQUIREMENTS)

    assert direct == [
        "mkdocs===1.6.1",
        "Pillow===12.2.0",
        "Pygments===2.20.0",
    ]
    assert all(ARBITRARY_EXACT_REQUIREMENT.fullmatch(line) for line in direct)


def test_documentation_dependency_graph_is_a_complete_arbitrary_exact_lock() -> None:
    locked = non_comment_lines(DOC_LOCK)

    assert locked == [
        "click===8.4.2",
        "ghp-import===2.1.0",
        "Jinja2===3.1.6",
        "Markdown===3.10.3",
        "MarkupSafe===3.0.3",
        "mergedeep===1.3.4",
        "mkdocs===1.6.1",
        "mkdocs-get-deps===0.2.2",
        "packaging===26.2",
        "pathspec===1.1.1",
        "Pillow===12.2.0",
        "platformdirs===4.11.0",
        "Pygments===2.20.0",
        "python-dateutil===2.9.0.post0",
        "PyYAML===6.0.3",
        "pyyaml-env-tag===1.1",
        "six===1.17.0",
        "watchdog===6.0.0",
    ]
    assert all(ARBITRARY_EXACT_REQUIREMENT.fullmatch(line) for line in locked)


def test_pages_actions_are_immutably_pinned() -> None:
    workflow = workflow_text()

    expected_actions = (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0",
        "actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b # v4",
        "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e # v4",
    )
    for action in expected_actions:
        assert action in workflow

    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" not in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" not in workflow
