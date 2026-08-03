from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_docs_environment import (
    compare_docs_distribution_sets,
    expected_docs_distribution_set,
)

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/verify_docs_environment.py"


def test_expected_docs_distribution_set_reads_arbitrary_exact_lock(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "requirements-docs.lock"
    lock.write_text(
        "Example_Package===1.2.3+local\n",
        encoding="utf-8",
    )

    assert expected_docs_distribution_set(lock) == {
        "example-package": "1.2.3+local"
    }


def test_expected_docs_distribution_set_rejects_matching_specifiers(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "requirements-docs.lock"
    lock.write_text("example-package==1.2.3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="arbitrary-exact"):
        expected_docs_distribution_set(lock)


def test_docs_distribution_set_accepts_only_lock_and_bootstrap_pip() -> None:
    expected = {"mkdocs": "1.6.1"}
    installed = {"mkdocs": "1.6.1", "pip": "26.1"}

    assert compare_docs_distribution_sets(expected, installed) == ()


def test_docs_distribution_set_rejects_extras_omissions_and_mismatches() -> None:
    expected = {"mkdocs": "1.6.1", "pygments": "2.20.0"}
    installed = {
        "mkdocs": "1.7.0",
        "injected-package": "9.9",
        "pip": "26.1",
    }

    errors = compare_docs_distribution_sets(expected, installed)

    assert any("missing expected distributions: pygments" in error for error in errors)
    assert any("injected-package==9.9" in error for error in errors)
    assert any(
        "mkdocs: expected 1.6.1, installed 1.7.0" in error for error in errors
    )


def test_docs_environment_verifier_supports_standalone_execution() -> None:
    completed = subprocess.run(
        [sys.executable, str(VERIFIER)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert "ModuleNotFoundError" not in completed.stderr
    assert completed.returncode in (0, 1)
