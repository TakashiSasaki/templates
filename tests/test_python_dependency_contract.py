"""Regression coverage for the static Python dependency boundary."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.check_python_dependencies import (
    ENVIRONMENTS,
    PythonEnvironment,
    environment_by_name,
    validate,
    validate_environment,
)


ROOT = Path(__file__).resolve().parents[1]


class PythonDependencyContractTests(unittest.TestCase):
    def test_current_ci_dependency_contracts_are_valid(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_visual_environment_requires_pyyaml_for_reachable_yaml_import(self) -> None:
        visual = environment_by_name("visual")
        with TemporaryDirectory() as directory:
            requirements = Path(directory) / "requirements-visual.txt"
            requirements.write_text(
                "\n".join(
                    line
                    for line in (ROOT / visual.requirements).read_text(encoding="utf-8").splitlines()
                    if not line.startswith("PyYAML")
                )
                + "\n",
                encoding="utf-8",
            )
            errors = validate_environment(
                ROOT,
                visual,
                requirements_path=requirements,
            )
        self.assertTrue(any("PyYAML" in error for error in errors), errors)

    def test_nested_production_imports_are_not_skipped(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements.txt").write_text("\n", encoding="utf-8")
            (root / "entrypoint.py").write_text(
                "def run():\n    import missing_nested_distribution\n",
                encoding="utf-8",
            )
            environment = PythonEnvironment(
                name="nested-fixture",
                requirements="requirements.txt",
                entrypoints=("entrypoint.py",),
            )
            errors = validate_environment(root, environment)
        self.assertTrue(
            any("missing_nested_distribution" in error for error in errors),
            errors,
        )

    def test_environment_inventory_has_distinct_requirements_inputs(self) -> None:
        self.assertEqual(
            {environment.name for environment in ENVIRONMENTS},
            {"core", "build", "visual", "composition-validation"},
        )
        self.assertEqual(
            len({environment.requirements for environment in ENVIRONMENTS}),
            len(ENVIRONMENTS),
        )
        self.assertTrue(environment_by_name("build").include_nested_imports)
