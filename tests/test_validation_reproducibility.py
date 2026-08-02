from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/contract-validation.yml"
DIRECT_REQUIREMENTS = ROOT / "requirements-dev.txt"
LOCKED_REQUIREMENTS = ROOT / "requirements-dev.lock"

EXPECTED_DIRECT_REQUIREMENTS = ("jsonschema==4.26.0",)
EXPECTED_LOCKED_REQUIREMENTS = (
    "attrs==26.1.0",
    "jsonschema==4.26.0",
    "jsonschema-specifications==2025.9.1",
    "referencing==0.37.0",
    "rpds-py==2026.6.3",
    "typing_extensions==4.16.0",
)
EXACT_REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+==[^=\s]+$")


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
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2",
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

    def test_workflow_installs_and_checks_only_the_locked_graph(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("cache-dependency-path: requirements-dev.lock", workflow)
        self.assertIn(
            "python -m pip install --disable-pip-version-check --requirement requirements-dev.lock",
            workflow,
        )
        self.assertNotIn("--requirement requirements-dev.txt", workflow)
        self.assertIn("python -m pip check", workflow)

    def test_workflow_exercises_both_public_validator_entry_points(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("python scripts/validate_contracts.py", workflow)
        self.assertIn("python -m scripts.validate_contracts", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)

    def test_direct_requirement_is_an_exact_reviewed_input(self) -> None:
        direct = requirement_lines(DIRECT_REQUIREMENTS)

        self.assertEqual(EXPECTED_DIRECT_REQUIREMENTS, direct)
        self.assertTrue(all(EXACT_REQUIREMENT.fullmatch(line) for line in direct))

    def test_lock_is_a_complete_exact_graph_for_the_selected_baseline(self) -> None:
        locked = requirement_lines(LOCKED_REQUIREMENTS)

        self.assertEqual(EXPECTED_LOCKED_REQUIREMENTS, locked)
        self.assertTrue(all(EXACT_REQUIREMENT.fullmatch(line) for line in locked))
        self.assertTrue(set(EXPECTED_DIRECT_REQUIREMENTS).issubset(locked))


if __name__ == "__main__":
    unittest.main()
