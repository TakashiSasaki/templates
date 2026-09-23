from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github/workflows/ci.yml"
CI_REQUIREMENTS = ROOT / "requirements-ci.txt"
CI_LOCK = ROOT / "requirements-ci.lock"
CI_ENVIRONMENT_VERIFIER = ROOT / "scripts/verify_ci_environment.py"

EXPECTED_DIRECT_REQUIREMENTS = (
    "editables===0.6",
    "hatchling===1.31.0",
    "Jinja2===3.1.6",
    "jsonschema===4.26.0",
    "Markdown===3.10.3",
    "Pygments===2.20.0",
    "pytest===8.4.2",
    "pytest-xdist===3.8.0",
    "PyYAML===6.0.3",
    "ruff===0.15.22",
)
EXPECTED_LOCKED_REQUIREMENTS = (
    "attrs===26.1.0",
    "editables===0.6",
    "execnet===2.1.2",
    "hatchling===1.31.0",
    "iniconfig===2.3.0",
    "Jinja2===3.1.6",
    "jsonschema===4.26.0",
    "jsonschema-specifications===2025.9.1",
    "Markdown===3.10.3",
    "MarkupSafe===3.0.3",
    "packaging===26.2",
    "pathspec===1.1.1",
    "pluggy===1.6.0",
    "Pygments===2.20.0",
    "pytest===8.4.2",
    "pytest-xdist===3.8.0",
    "PyYAML===6.0.3",
    "referencing===0.37.0",
    "rpds-py===2026.6.3",
    "ruff===0.15.22",
    "trove-classifiers===2026.6.1.19",
    "typing_extensions===4.16.0",
)
ARBITRARY_EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9_.-]+===[A-Za-z0-9][A-Za-z0-9._+!-]*$"
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
    "PIP_EDITABLE",
    "PIP_GROUP",
    "PIP_REQUIREMENTS_FROM_SCRIPT",
    "PIP_REPORT",
    "PIP_CONFIG_SETTINGS",
    "PIP_IGNORE_REQUIRES_PYTHON",
    "PIP_LOG",
)


def non_comment_lines(path: Path) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_policy_ci_uses_runner_python_without_runtime_selection() -> None:
    workflow = workflow_text()

    assert "runs-on: ubuntu-24.04" in workflow
    assert "runs-on: ubuntu-latest" not in workflow
    assert "actions/setup-python" not in workflow
    assert "python-version" not in workflow
    assert "windows-" not in workflow


def test_policy_ci_clears_external_python_and_pip_inputs_before_bootstrap() -> None:
    workflow = workflow_text()
    readme = README.read_text(encoding="utf-8")

    assert '      PYTHONHOME: ""' in workflow
    assert '      PYTHONPATH: ""' in workflow
    assert '      PYTHONNOUSERSITE: "1"' in workflow
    assert '      PIP_PYTHON: ""' in workflow
    assert '      PIP_CACHE_DIR: ""' in workflow
    assert '      PIP_NO_CACHE_DIR: ""' in workflow
    assert '      PIP_QUIET: ""' in workflow
    assert '      PIP_LOG: ""' in workflow
    assert "      PIP_CONFIG_FILE: /dev/null" in workflow
    documented_unset = (
        "unset PYTHONHOME PYTHONPATH PYTHONUSERBASE "
        + " ".join(PIP_SANITIZED_INPUTS)
    )
    documented_sequence = (
        f"{documented_unset}\n"
        "export PIP_CONFIG_FILE=/dev/null\n"
        "python3 -I -m venv --clear .venv\n"
        ". .venv/bin/activate"
    )
    assert documented_sequence in readme
    assert "python -m venv --clear .venv" not in readme
    assert "python -m venv .venv" not in readme


def test_policy_ci_uses_an_isolated_bootstrap_interpreter_and_cleared_venv() -> None:
    workflow = workflow_text()

    assert "run: python3 -I -m venv --clear .venv" in workflow
    assert "run: python -I -m venv --clear .venv" not in workflow
    assert "--system-site-packages" not in workflow


def test_policy_ci_installs_only_the_locked_dependency_graph() -> None:
    workflow = workflow_text()
    workflow_unsets = " ".join(f"-u {name}" for name in PIP_SANITIZED_INPUTS)

    assert "cache-dependency-path:" not in workflow
    assert (
        f"env {workflow_unsets} .venv/bin/python -m pip install "
        "--disable-pip-version-check --no-deps --requirement requirements-ci.lock"
    ) in workflow
    assert (
        f"env {workflow_unsets} .venv/bin/python -m pip install "
        "--disable-pip-version-check --no-deps --no-build-isolation -e ."
    ) in workflow
    assert "--requirement requirements-ci.txt" not in workflow
    assert "-e '.[dev]'" not in workflow


def test_stable_release_probe_sanitizes_inherited_pip_inputs() -> None:
    workflow = workflow_text()
    runner = (ROOT / "scripts/run_policy_preflight.py").read_text(encoding="utf-8")

    assert "POLICY_SOURCE_REF: refs/remotes/origin/policy-source" in workflow
    assert "scripts/run_policy_preflight.py --check release-state" in workflow
    assert 'if not key.startswith("PIP_") and not key.startswith("PYTHON")' in runner
    assert 'environment["PIP_CONFIG_FILE"] = os.devnull' in runner


def test_policy_ci_verifies_the_complete_installed_distribution_set() -> None:
    workflow = workflow_text()
    readme = README.read_text(encoding="utf-8")

    assert CI_ENVIRONMENT_VERIFIER.is_file()
    assert "run: .venv/bin/python scripts/run_policy_preflight.py --check environment" in workflow
    assert "python3 scripts/verify_ci_environment.py" in readme
    runner = (ROOT / "scripts/run_policy_preflight.py").read_text(encoding="utf-8")
    assert 'run(sys.executable, "scripts/verify_ci_environment.py")' in runner
    assert 'run(sys.executable, "-m", "pip", "check")' in runner
    assert "run: python -m pip check" not in workflow


def test_policy_ci_runs_all_python_tooling_from_the_isolated_environment() -> None:
    workflow = workflow_text()

    expected_commands = (
        ".venv/bin/python scripts/run_policy_preflight.py --check release-state",
        ".venv/bin/python scripts/run_policy_preflight.py --check lint",
        ".venv/bin/python scripts/run_policy_preflight.py --check tests",
        ".venv/bin/python scripts/run_policy_preflight.py --check installed-command",
        "python3 -I scripts/run_policy_preflight.py --check compile",
    )
    for command in expected_commands:
        assert command in workflow

    forbidden_commands = (
        "run: python scripts/verify-release-state.py",
        "run: pytest",
        "run: python -m compileall",
        "run: agent-policy --help",
        ".venv/bin/python -m ruff check src tests scripts skills/agent-policy/scripts",
    )
    for command in forbidden_commands:
        assert command not in workflow


def test_ci_dependency_inputs_are_arbitrary_exact_reviewed_pins() -> None:
    direct = non_comment_lines(CI_REQUIREMENTS)

    assert direct == EXPECTED_DIRECT_REQUIREMENTS
    assert all(ARBITRARY_EXACT_REQUIREMENT.fullmatch(line) for line in direct)


def test_ci_dependency_graph_is_a_complete_arbitrary_exact_lock() -> None:
    locked = non_comment_lines(CI_LOCK)

    assert locked == EXPECTED_LOCKED_REQUIREMENTS
    assert all(ARBITRARY_EXACT_REQUIREMENT.fullmatch(line) for line in locked)
    assert set(EXPECTED_DIRECT_REQUIREMENTS).issubset(locked)


def test_arbitrary_exact_pins_reject_matching_and_local_variant_specifiers() -> None:
    invalid_requirements = (
        "jsonschema==4.26.0",
        "jsonschema==4.26.*",
        "jsonschema>=4.26.0",
        'jsonschema===4.26.0; python_version < "3.13"',
    )

    for requirement in invalid_requirements:
        assert ARBITRARY_EXACT_REQUIREMENT.fullmatch(requirement) is None

    assert ARBITRARY_EXACT_REQUIREMENT.fullmatch("jsonschema===4.26.0")
    assert ARBITRARY_EXACT_REQUIREMENT.fullmatch("jsonschema===4.26.0+corp")
    assert "jsonschema===4.26.0" != "jsonschema===4.26.0+corp"


def test_policy_ci_actions_are_immutably_pinned() -> None:
    workflow = workflow_text()

    expected_actions = (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
    )
    for action in expected_actions:
        assert action in workflow

    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" not in workflow
    assert "actions/setup-python" not in workflow


def test_all_policy_workflows_use_runner_python_without_version_setup() -> None:
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = path.read_text(encoding="utf-8")
        assert "actions/setup-python" not in workflow, path.name
        assert "python-version" not in workflow, path.name
        assert "windows-" not in workflow.lower(), path.name
