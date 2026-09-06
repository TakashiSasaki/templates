from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github/workflows/pages.yml"
PUBLICATION_GUIDE = ROOT / "docs/documentation-publication.md"
DOC_REQUIREMENTS = ROOT / "requirements-docs.txt"
DOC_LOCK = ROOT / "requirements-docs.lock"
DOC_ENVIRONMENT_VERIFIER = ROOT / "scripts/verify_docs_environment.py"
ARBITRARY_EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9_.-]+===[A-Za-z0-9][A-Za-z0-9._+!-]*$"
)
PYTHON_SANITIZED_INPUTS = (
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


def test_documentation_workflow_targets_policy_and_its_pr_stacks() -> None:
    workflow = workflow_text()

    assert "push:\n    branches: [policy]" in workflow
    assert 'branches: [policy, "policy-*"]' in workflow
    assert "branches: [skill]" not in workflow
    assert "branches: [main]" not in workflow
    assert "branches: [site]" not in workflow
    assert "workflow_dispatch" not in workflow
    assert "workflow_call" not in workflow
    assert "bootstrap-agent-policy:refs" not in workflow
    assert "git fetch" not in workflow


def test_policy_documentation_has_no_pages_deployment_route() -> None:
    workflow = workflow_text()

    assert "name: Policy documentation build" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "\njobs:\n  build:" in workflow
    assert "\n  deploy:" not in workflow
    for forbidden in (
        "pages: write",
        "id-token: write",
        "name: github-pages",
        "actions/upload-pages-artifact@",
        "actions/configure-pages@",
        "actions/deploy-pages@",
        "false &&",
    ):
        assert forbidden not in workflow


def test_documentation_build_uses_the_validated_runner_and_python_release() -> None:
    workflow = workflow_text()

    assert workflow.count("runs-on: ubuntu-24.04") == 1
    assert "runs-on: ubuntu-latest" not in workflow
    assert 'python-version: "3.12.13"' in workflow
    assert 'python-version: "3.12"' not in workflow


def test_documentation_build_clears_external_inputs_before_setup() -> None:
    workflow = workflow_text()

    for name in PYTHON_SANITIZED_INPUTS:
        assert f'      {name}: ""' in workflow
    assert '      PYTHONNOUSERSITE: "1"' in workflow

    for name in (
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
    ):
        assert f'      {name}: ""' in workflow

    assert "      PIP_CONFIG_FILE: /dev/null" in workflow


def test_documentation_build_uses_a_cleared_isolated_environment() -> None:
    workflow = workflow_text()

    assert "run: python -I -m venv --clear .venv" in workflow
    assert "run: python -m venv --clear .venv" not in workflow
    assert "--system-site-packages" not in workflow


def test_documentation_build_installs_and_verifies_only_the_lock() -> None:
    workflow = workflow_text()
    workflow_unsets = " ".join(f"-u {name}" for name in PIP_SANITIZED_INPUTS)

    assert "cache-dependency-path: requirements-docs.lock" in workflow
    assert (
        f"run: env {workflow_unsets} .venv/bin/python -m pip install "
        "--isolated --disable-pip-version-check --no-deps "
        "--requirement requirements-docs.lock"
    ) in workflow
    assert "run: .venv/bin/python scripts/verify_docs_environment.py" in workflow
    assert "run: .venv/bin/python -m pip check" in workflow
    assert "-r requirements-docs.lock" not in workflow
    assert "-r requirements-docs.txt" not in workflow


def test_documentation_build_runs_all_tools_from_the_isolated_environment() -> None:
    workflow = workflow_text()

    required_steps = (
        ".venv/bin/python scripts/generate_repository_preview.py",
        ".venv/bin/python scripts/verify-repository-structure.py --check",
        ".venv/bin/python scripts/generate-doc-assets.py",
        ".venv/bin/python scripts/generate_docs_build_info.py",
        ".venv/bin/python -m mkdocs build --strict --clean",
    )
    for step in required_steps:
        assert step in workflow

    assert "BUILD_COMMIT: ${{ github.sha }}" in workflow
    assert '--repository "$BUILD_REPOSITORY"' in workflow
    assert "from datetime import datetime, timezone" not in workflow


def test_documentation_environment_contract_is_documented() -> None:
    readme = README.read_text(encoding="utf-8")
    guide = PUBLICATION_GUIDE.read_text(encoding="utf-8")
    documented_unset = (
        "unset "
        + " ".join(PYTHON_SANITIZED_INPUTS)
        + " "
        + " ".join(PIP_SANITIZED_INPUTS)
    )
    documented_sequence = (
        f"{documented_unset}\n"
        "export PIP_CONFIG_FILE=/dev/null\n"
        "python -I -m venv --clear .venv\n"
        ". .venv/bin/activate\n"
        "python -m pip install --isolated --disable-pip-version-check "
        "--no-deps --requirement requirements-docs.lock\n"
        "python scripts/verify_docs_environment.py\n"
        "python -m pip check"
    )

    assert documented_sequence in guide
    assert "CPython 3.12.13" in guide
    assert "Ubuntu 24.04" in guide
    assert "documentation build uses the same clean-runner boundary" in readme
    assert "contains no GitHub Pages deployment route" in guide
    assert "contains no GitHub Pages deployment route" in readme


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
    assert set(non_comment_lines(DOC_REQUIREMENTS)).issubset(locked)


def test_documentation_environment_verifier_is_present() -> None:
    assert DOC_ENVIRONMENT_VERIFIER.is_file()


def test_documentation_actions_are_immutably_pinned() -> None:
    workflow = workflow_text()

    expected_actions = (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0",
    )
    for action in expected_actions:
        assert action in workflow

    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" not in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" not in workflow
    assert "actions/checkout@v" not in workflow
    assert "actions/setup-python@v" not in workflow
