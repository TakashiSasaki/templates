from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_ci_environment import (
    compare_distribution_sets,
    expected_distribution_set,
    load_local_project,
    load_locked_requirements,
    normalize_distribution_name,
)


def test_normalize_distribution_name_uses_python_packaging_normalization() -> None:
    assert normalize_distribution_name("Typing_Extensions") == "typing-extensions"
    assert normalize_distribution_name("takashisasaki.agent_policy") == (
        "takashisasaki-agent-policy"
    )


def test_load_locked_requirements_accepts_only_arbitrary_exact_entries(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("Example_Package===1.2.3+local\n", encoding="utf-8")

    assert load_locked_requirements(lock) == {"example-package": "1.2.3+local"}

    lock.write_text("example-package==1.2.3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="arbitrary-exact"):
        load_locked_requirements(lock)


def test_load_locked_requirements_rejects_duplicate_normalized_names(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "Example_Package===1.2.3\nexample-package===1.2.3\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate distribution example-package"):
        load_locked_requirements(lock)


def test_local_project_metadata_is_loaded_from_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "Example_Project"\nversion = "2.0.0"\n',
        encoding="utf-8",
    )

    assert load_local_project(pyproject) == ("example-project", "2.0.0")


def test_expected_set_combines_lock_and_local_project(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("dependency===1.0\n", encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "local-project"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    assert expected_distribution_set(lock, pyproject) == {
        "dependency": "1.0",
        "local-project": "0.1.0",
    }


def test_distribution_set_accepts_only_lock_project_and_bootstrap_pip() -> None:
    expected = {"dependency": "1.0", "local-project": "0.1.0"}
    installed = {
        "dependency": "1.0",
        "local-project": "0.1.0",
        "pip": "26.1",
    }

    assert compare_distribution_sets(expected, installed) == ()


def test_distribution_set_rejects_extras_omissions_and_version_mismatches() -> None:
    expected = {"dependency": "1.0", "local-project": "0.1.0"}
    installed = {
        "dependency": "2.0",
        "injected-package": "9.9",
        "pip": "26.1",
    }

    errors = compare_distribution_sets(expected, installed)

    assert any("missing expected distributions: local-project" in error for error in errors)
    assert any("injected-package==9.9" in error for error in errors)
    assert any("dependency: expected 1.0, installed 2.0" in error for error in errors)
