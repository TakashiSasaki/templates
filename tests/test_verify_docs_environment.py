from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_docs_environment import (
    compare_distribution_sets,
    load_locked_requirements,
    normalize_distribution_name,
)


def test_normalize_distribution_name_uses_python_packaging_normalization() -> None:
    assert normalize_distribution_name("Typing_Extensions") == "typing-extensions"
    assert normalize_distribution_name("mkdocs_get_deps") == "mkdocs-get-deps"


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


def test_load_locked_requirements_rejects_an_empty_lock(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("# no distributions\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not be empty"):
        load_locked_requirements(lock)


def test_distribution_set_accepts_only_lock_and_bootstrap_pip() -> None:
    expected = {"mkdocs": "1.6.1", "pyyaml": "6.0.3"}
    installed = {
        "mkdocs": "1.6.1",
        "PyYAML": "6.0.3",
        "pip": "26.1",
    }

    assert compare_distribution_sets(expected, installed) == ()


def test_distribution_set_rejects_extras_omissions_and_version_mismatches() -> None:
    expected = {"mkdocs": "1.6.1", "pyyaml": "6.0.3"}
    installed = {
        "mkdocs": "2.0.0",
        "injected-package": "9.9",
        "pip": "26.1",
    }

    errors = compare_distribution_sets(expected, installed)

    assert any("missing expected distributions: pyyaml" in error for error in errors)
    assert any("injected-package==9.9" in error for error in errors)
    assert any("mkdocs: expected 1.6.1, installed 2.0.0" in error for error in errors)
