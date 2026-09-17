from __future__ import annotations

from pathlib import Path

from scripts.check_python_dependencies import (
    Environment,
    validate,
    validate_environment,
)

ROOT = Path(__file__).resolve().parents[1]


def test_current_policy_dependency_boundaries_are_declared() -> None:
    assert validate(ROOT) == []


def test_missing_pyyaml_from_release_environment_fails_closed(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.lock"
    requirements.write_text(
        "jsonschema==4.26.0\n",
        encoding="utf-8",
    )
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    entrypoint = scripts / "entrypoint.py"
    entrypoint.write_text("import yaml\n", encoding="utf-8")
    environment = Environment("fixture", "requirements.lock", ("scripts/entrypoint.py",))
    errors = validate_environment(tmp_path, environment)
    assert any("PyYAML" in error for error in errors), errors
