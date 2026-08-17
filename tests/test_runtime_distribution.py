from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

from scripts.verify_ci_environment import load_locked_requirements as load_ci_lock
from scripts.verify_runtime_environment import (
    compare_distribution_sets,
    load_locked_requirements,
    normalize_distribution_name,
)

ROOT = Path(__file__).resolve().parents[1]


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
