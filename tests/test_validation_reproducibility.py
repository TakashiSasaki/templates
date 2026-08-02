from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.verify_locked_environment import compare_distribution_sets

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github/workflows/contract-validation.yml"
TOOLCHAIN_GUIDE = ROOT / "docs/architecture/validation-toolchain.md"
DIRECT_REQUIREMENTS = ROOT / "requirements-dev.txt"
LOCKED_REQUIREMENTS = ROOT / "requirements-dev.lock"
LOCK_VERIFIER = ROOT / "scripts/verify_locked_environment.py"

EXPECTED_DIRECT_REQUIREMENTS = ("jsonschema===4.26.0",)
EXPECTED_LOCKED_REQUIREMENTS = (
    "attrs===26.1.0",
    "jsonschema===4.26.0",
    "jsonschema-specifications===2025.9.1",
    "referencing===0.37.0",
    "rpds-py===2026.6.3",
    "typing_extensions===4.16.0",
)
ARBITRARY_EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9_.-]+===[A-Za-z0-9][A-Za-z0-9._+!-]*$"
)


def requirement_lines(path: Path) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


class ValidationReproducibilityTests(unittest.TestCase):
    def test_workflow_pins_runner_node24_actions_and_python_patch(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertNotIn("ubuntu-latest", workflow)
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            workflow,
        )
        self.assertIn(
            "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0",
            workflow,
        )
        self.assertNotRegex(workflow, r"actions/(?:checkout|setup-python)@v\d")
        self.assertNotIn("# v4.", workflow)
        self.assertNotIn("# v5.", workflow)
        self.assertIn('python-version: "3.12.13"', workflow)

    def test_validation_environments_are_cleared_before_recreation(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        toolchain_guide = TOOLCHAIN_GUIDE.read_text(encoding="utf-8")

        for source_name, source in (
            ("workflow", workflow),
            ("README", readme),
            ("toolchain guide", toolchain_guide),
        ):
            with self.subTest(source=source_name):
                self.assertIn("python -m venv --clear .venv", source)
                self.assertNotIn("python -m venv .venv", source)

    def test_pythonpath_is_cleared_before_any_python_invocation(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        toolchain_guide = TOOLCHAIN_GUIDE.read_text(encoding="utf-8")

        self.assertIn('      PYTHONPATH: ""', workflow)
        documented_sequence = (
            "unset PYTHONPATH PIP_REQUIREMENT PIP_CONSTRAINT PIP_EDITABLE\n"
            "export PIP_CONFIG_FILE=/dev/null\n"
            "python -m venv --clear .venv\n"
            ". .venv/bin/activate"
        )
        unsafe_sequence = (
            "python -m venv --clear .venv\n"
            ". .venv/bin/activate\n"
            "unset PYTHONPATH"
        )
        self.assertIn(documented_sequence, readme)
        self.assertIn(documented_sequence, toolchain_guide)
        self.assertNotIn(unsafe_sequence, readme)
        self.assertNotIn(unsafe_sequence, toolchain_guide)

    def test_pip_injection_is_disabled_and_installed_set_is_verified(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        toolchain_guide = TOOLCHAIN_GUIDE.read_text(encoding="utf-8")

        self.assertTrue(LOCK_VERIFIER.is_file())
        self.assertIn("      PIP_CONFIG_FILE: /dev/null", workflow)
        self.assertIn(
            "run: env -u PIP_REQUIREMENT -u PIP_CONSTRAINT -u PIP_EDITABLE .venv/bin/python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock",
            workflow,
        )
        self.assertIn(
            "run: .venv/bin/python scripts/verify_locked_environment.py",
            workflow,
        )
        for source_name, source in (
            ("README", readme),
            ("toolchain guide", toolchain_guide),
        ):
            with self.subTest(source=source_name):
                self.assertIn(
                    "unset PYTHONPATH PIP_REQUIREMENT PIP_CONSTRAINT PIP_EDITABLE",
                    source,
                )
                self.assertIn("export PIP_CONFIG_FILE=/dev/null", source)
                self.assertIn("python scripts/verify_locked_environment.py", source)

    def test_distribution_set_verifier_rejects_injected_packages(self) -> None:
        expected = {"jsonschema": "4.26.0"}
        installed = {
            "jsonschema": "4.26.0",
            "injected-package": "1.0",
            "pip": "26.1",
        }

        errors = compare_distribution_sets(expected, installed)

        self.assertTrue(any("unexpected distributions" in error for error in errors))
        self.assertTrue(any("injected-package==1.0" in error for error in errors))

    def test_distribution_set_verifier_accepts_only_lock_plus_bootstrap_pip(self) -> None:
        expected = {"jsonschema": "4.26.0"}
        installed = {"jsonschema": "4.26.0", "pip": "26.1"}

        self.assertEqual((), compare_distribution_sets(expected, installed))

    def test_workflow_creates_a_fresh_isolated_virtual_environment(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("run: python -m venv --clear .venv", workflow)
        self.assertNotIn("--system-site-packages", workflow)

    def test_workflow_installs_and_checks_only_the_locked_graph(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("cache-dependency-path: requirements-dev.lock", workflow)
        self.assertIn(
            "env -u PIP_REQUIREMENT -u PIP_CONSTRAINT -u PIP_EDITABLE .venv/bin/python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock",
            workflow,
        )
        self.assertNotIn(
            "run: python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock",
            workflow,
        )
        self.assertNotIn("--requirement requirements-dev.txt", workflow)
        self.assertIn("run: .venv/bin/python -m pip check", workflow)
        self.assertNotIn("run: python -m pip check", workflow)

    def test_readme_installation_is_dependency_isolated(self) -> None:
        readme = README.read_text(encoding="utf-8")

        self.assertIn(
            "python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock",
            readme,
        )
        self.assertNotIn(
            "python -m pip install --disable-pip-version-check --requirement requirements-dev.lock",
            readme,
        )

    def test_workflow_exercises_both_public_validator_entry_points_in_the_venv(
        self,
    ) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "run: .venv/bin/python scripts/validate_contracts.py", workflow
        )
        self.assertIn(
            "run: .venv/bin/python -m scripts.validate_contracts", workflow
        )
        self.assertIn(
            "run: .venv/bin/python -m unittest discover -s tests -v", workflow
        )
        self.assertNotIn("run: python scripts/validate_contracts.py", workflow)
        self.assertNotIn("run: python -m scripts.validate_contracts", workflow)
        self.assertNotIn("run: python -m unittest discover -s tests -v", workflow)

    def test_arbitrary_exact_pattern_rejects_pep440_matching_specifiers(self) -> None:
        invalid_requirements = (
            "jsonschema==4.26.0",
            "jsonschema==4.26.*",
            "jsonschema==4.26.*,!=4.26.1",
            'jsonschema===4.26.0; python_version < "3.13"',
            "jsonschema===https://example.invalid/jsonschema.whl",
        )

        for requirement in invalid_requirements:
            with self.subTest(requirement=requirement):
                self.assertIsNone(ARBITRARY_EXACT_REQUIREMENT.fullmatch(requirement))

        self.assertIsNotNone(
            ARBITRARY_EXACT_REQUIREMENT.fullmatch(
                "example===1!2.3rc1.post2.dev3+linux_x86_64"
            )
        )

    def test_public_version_pin_excludes_unrequested_local_variants(self) -> None:
        self.assertIsNotNone(
            ARBITRARY_EXACT_REQUIREMENT.fullmatch("jsonschema===4.26.0")
        )
        self.assertIsNotNone(
            ARBITRARY_EXACT_REQUIREMENT.fullmatch("jsonschema===4.26.0+corp")
        )
        self.assertNotEqual("jsonschema===4.26.0", "jsonschema===4.26.0+corp")

    def test_direct_requirement_is_an_arbitrary_exact_reviewed_input(self) -> None:
        direct = requirement_lines(DIRECT_REQUIREMENTS)

        self.assertEqual(EXPECTED_DIRECT_REQUIREMENTS, direct)
        self.assertTrue(
            all(ARBITRARY_EXACT_REQUIREMENT.fullmatch(line) for line in direct)
        )

    def test_lock_is_a_complete_arbitrary_exact_graph_for_the_selected_baseline(self) -> None:
        locked = requirement_lines(LOCKED_REQUIREMENTS)

        self.assertEqual(EXPECTED_LOCKED_REQUIREMENTS, locked)
        self.assertTrue(
            all(ARBITRARY_EXACT_REQUIREMENT.fullmatch(line) for line in locked)
        )
        self.assertTrue(set(EXPECTED_DIRECT_REQUIREMENTS).issubset(locked))


if __name__ == "__main__":
    unittest.main()
