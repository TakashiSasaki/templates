from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement

from scripts.run_policy_runtime_checks import commands_for
from scripts.smoke_test_runtime_distribution import environment as smoke_environment
from scripts.verify_ci_environment import load_locked_requirements as load_ci_lock
from scripts.verify_runtime_environment import (
    compare_distribution_sets,
    load_locked_requirements,
    normalize_distribution_name,
)

ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> tuple[str, dict[str, object]]:
    text = (ROOT / ".github/workflows/runtime-distribution.yml").read_text(
        encoding="utf-8"
    )
    return text, yaml.load(text, Loader=yaml.BaseLoader)


def test_runtime_lock_is_synchronized_with_ci_lock() -> None:
    runtime = load_locked_requirements(ROOT / "requirements-runtime.lock")
    ci = load_ci_lock(ROOT / "requirements-ci.lock")

    assert runtime
    assert set(runtime) <= set(ci)
    assert {name: ci[name] for name in runtime} == runtime


def test_runtime_lock_covers_declared_project_dependencies() -> None:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = document["project"]
    declared = {
        normalize_distribution_name(Requirement(value).name)
        for value in project["dependencies"]
    }
    locked = load_locked_requirements(ROOT / "requirements-runtime.lock")

    assert declared <= set(locked)


def test_smoke_environment_removes_external_python_and_pip_inputs() -> None:
    cleaned = smoke_environment(
        {
            "PATH": "runtime-path",
            "OTHER_INPUT": "preserved",
            "PYTHONHOME": "host-python",
            "pythonpath": "host-imports",
            "PYTHONUSERBASE": "host-user-base",
            "PIP_INDEX_URL": "https://example.invalid/simple",
            "pip_constraint": "host-constraint.txt",
            "PIP_CONFIG_FILE": "host-pip.conf",
        }
    )

    assert cleaned["PATH"] == "runtime-path"
    assert cleaned["OTHER_INPUT"] == "preserved"
    assert cleaned["PYTHONNOUSERSITE"] == "1"
    assert cleaned["PIP_CONFIG_FILE"] == os.devnull
    assert cleaned["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert not {
        key
        for key in cleaned
        if key.upper().startswith("PYTHON") and key != "PYTHONNOUSERSITE"
    }
    assert not {
        key
        for key in cleaned
        if key.upper().startswith("PIP_")
        and key not in {"PIP_CONFIG_FILE", "PIP_DISABLE_PIP_VERSION_CHECK"}
    }


def test_runtime_workflow_does_not_use_pip_cache_before_sanitization() -> None:
    workflow, _document = _workflow()

    assert "cache: pip" not in workflow
    assert "PIP_CONFIG_FILE:" in workflow
    assert "PYTHONHOME:" in workflow
    assert "PYTHONPATH:" in workflow
    assert "scripts/run_policy_runtime_checks.py" in workflow


def test_runtime_workflow_trigger_tiers_are_exact() -> None:
    _workflow_text, document = _workflow()

    triggers = document["on"]
    assert set(triggers) == {"push", "pull_request"}
    assert triggers["push"] == {"branches": ["policy"]}
    assert triggers["pull_request"] == {
        "types": ["opened", "synchronize", "reopened", "labeled", "unlabeled"],
    }
    assert "schedule" not in triggers
    assert "workflow_dispatch" not in triggers


def test_runtime_workflow_classifies_before_selecting_tier() -> None:
    workflow, document = _workflow()
    jobs = document["jobs"]

    classifier = jobs["classify_runtime"]
    assert classifier["runs-on"] == "ubuntu-24.04"
    assert classifier["outputs"]["required"] == "${{ steps.classify.outputs.required }}"
    command = classifier["steps"][1]["run"]
    assert "scripts/classify_runtime_distribution_ci.py" in command
    assert "--force-compatibility" not in command
    assert "compatibility_requested" not in workflow
    classifier_text = workflow.split("\n  classify_runtime:\n", 1)[1].split(
        "\n  runtime-checks:\n", 1
    )[0]
    assert "ci/full-compatibility" not in classifier_text
    assert "refs/tags/policy-compatibility-" not in classifier_text
    assert "github.event.before" in classifier_text


def test_runtime_workflow_uses_one_ubuntu_runner_python_job() -> None:
    workflow, document = _workflow()
    jobs = document["jobs"]
    baseline = jobs["runtime-checks"]

    assert baseline["runs-on"] == "ubuntu-24.04"
    assert baseline["needs"] == ["classify_runtime"]
    assert "needs.classify_runtime.outputs.required == 'true'" in baseline["if"]
    assert "strategy" not in baseline
    command = baseline["steps"][-1]["run"]
    assert "python3 -I" in command
    assert "scripts/run_policy_runtime_checks.py" in command
    assert "--check all" in command
    assert "--revision" in command
    assert "actions/setup-python" not in workflow
    assert "python-version" not in workflow
    assert "windows-" not in workflow


def test_runtime_workflow_has_no_obsolete_duplicate_jobs() -> None:
    _workflow_text, document = _workflow()
    jobs = document["jobs"]

    assert "clean-install" not in jobs
    assert "skill-source-candidate" not in jobs
    assert set(jobs) == {"classify_runtime", "runtime-checks", "validate"}


def test_runtime_workflow_final_gate_enforces_skip_and_success_semantics() -> None:
    _workflow_text, document = _workflow()
    validate = document["jobs"]["validate"]

    assert validate["if"] == "${{ always() }}"
    assert validate["needs"] == [
        "classify_runtime",
        "runtime-checks",
    ]
    run = validate["steps"][0]["run"]
    assert 'test "$CLASSIFIER_RESULT" = success' in run
    assert 'test "$RUNTIME_CHECKS_RESULT" = success' in run
    assert 'test "$RUNTIME_CHECKS_RESULT" = skipped' in run
    assert "COMPATIBILITY_RUNTIME_RESULT" not in run
    assert "invalid runtime classification" in run


def test_canonical_runner_matches_local_and_ci_commands() -> None:
    revision = "a" * 40
    commands = commands_for("all", revision)

    assert commands == (
        (
            sys.executable,
            "-I",
            str(ROOT / "scripts/run_policy_preflight.py"),
            "--check",
            "runtime",
        ),
        (
            sys.executable,
            "-I",
            str(ROOT / "scripts/smoke_test_agent_policy_skill_source.py"),
            "--revision",
            revision,
        ),
    )
    assert commands_for("runtime", None) == (commands[0],)
    assert commands_for("skill-source", revision) == (commands[1],)
    with pytest.raises(ValueError, match="--revision is required"):
        commands_for("skill-source", None)


def test_runtime_verifier_imports_shared_helpers_under_isolated_python() -> None:
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import runpy; runpy.run_path('scripts/verify_runtime_environment.py')",
        ],
        cwd=ROOT,
        check=True,
    )


def test_runtime_verifier_accepts_exact_locked_distribution_set() -> None:
    errors = compare_distribution_sets(
        {"Jinja2": "3.1.6", "MarkupSafe": "3.0.3"},
        {
            "pip": "25.0",
            "takashisasaki-agent-policy": "0.1.0",
            "Jinja2": "3.1.6",
            "MarkupSafe": "3.0.3",
        },
        project_name="takashisasaki-agent-policy",
        project_version="0.1.0",
    )

    assert errors == ()


def test_runtime_verifier_rejects_project_duplicated_in_lock() -> None:
    errors = compare_distribution_sets(
        {
            "takashisasaki-agent-policy": "0.1.0",
            "Jinja2": "3.1.6",
        },
        {
            "takashisasaki-agent-policy": "0.1.0",
            "Jinja2": "3.1.6",
        },
        project_name="takashisasaki-agent-policy",
        project_version="0.1.0",
    )

    assert errors == (
        "runtime lock must not contain the local project distribution: "
        "takashisasaki-agent-policy",
    )


def test_runtime_verifier_rejects_missing_locked_distribution() -> None:
    errors = compare_distribution_sets(
        {"Jinja2": "3.1.6", "MarkupSafe": "3.0.3"},
        {
            "takashisasaki-agent-policy": "0.1.0",
            "Jinja2": "3.1.6",
        },
        project_name="takashisasaki-agent-policy",
        project_version="0.1.0",
    )

    assert errors == ("missing locked runtime distributions: markupsafe",)


def test_runtime_verifier_rejects_unlocked_distribution() -> None:
    errors = compare_distribution_sets(
        {"Jinja2": "3.1.6"},
        {
            "takashisasaki-agent-policy": "0.1.0",
            "Jinja2": "3.1.6",
            "mystery-package": "1.0.0",
        },
        project_name="takashisasaki-agent-policy",
        project_version="0.1.0",
    )

    assert errors == (
        "installed runtime distributions missing from lock: mystery-package==1.0.0",
    )


def test_runtime_verifier_rejects_version_drift() -> None:
    errors = compare_distribution_sets(
        {"Jinja2": "3.1.6"},
        {
            "takashisasaki-agent-policy": "0.1.0",
            "Jinja2": "3.1.5",
        },
        project_name="takashisasaki-agent-policy",
        project_version="0.1.0",
    )

    assert errors == (
        "runtime dependency version mismatches: jinja2: expected 3.1.6, installed 3.1.5",
    )
