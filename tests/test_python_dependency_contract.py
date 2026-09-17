"""Regression coverage for the static Python dependency boundary."""
from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import yaml

from scripts.check_python_dependencies import (
    ENVIRONMENTS,
    PythonEnvironment,
    VISUAL_ENTRYPOINTS,
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

    def test_visual_inventory_covers_python_scripts_in_browser_workflow(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/build-pages.yml").read_text(encoding="utf-8")
        )
        check_runs = "\n".join(
            str(step.get("run", ""))
            for step in workflow["jobs"]["check"]["steps"]
            if isinstance(step, dict)
        )
        workflow_entrypoints = set(
            re.findall(r"\bpython(?:3)?\s+(scripts/[A-Za-z0-9_-]+\.py)", check_runs)
        )
        workflow_entrypoints.discard("scripts/check_python_dependencies.py")
        self.assertTrue(workflow_entrypoints)
        self.assertTrue(
            workflow_entrypoints <= set(VISUAL_ENTRYPOINTS),
            sorted(workflow_entrypoints - set(VISUAL_ENTRYPOINTS)),
        )

    def test_acquisition_entrypoint_undeclared_import_fails_visual_contract(self) -> None:
        visual = environment_by_name("visual")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts/acquire_integration_bundle.py").write_text(
                "import undeclared_acquisition_distribution\n",
                encoding="utf-8",
            )
            requirements = root / "requirements-visual.txt"
            requirements.write_text("playwright==1.61.0\n", encoding="utf-8")
            acquisition_environment = PythonEnvironment(
                name=visual.name,
                requirements=visual.requirements,
                entrypoints=("scripts/acquire_integration_bundle.py",),
                required_distributions=visual.required_distributions,
            )
            errors = validate_environment(root, acquisition_environment)
        self.assertIn("scripts/acquire_integration_bundle.py", VISUAL_ENTRYPOINTS)
        self.assertTrue(
            any("undeclared_acquisition_distribution" in error for error in errors),
            errors,
        )

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
