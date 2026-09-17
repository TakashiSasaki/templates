from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from scripts.check_python_dependencies import Environment, validate, validate_environment

ROOT = Path(__file__).resolve().parents[1]
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*===([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if EXACT_REQUIREMENT.fullmatch(value) is None:
            raise AssertionError(
                f"{path.name}:{line_number}: expected exact name===version entry"
            )
        name, version = value.split("===", 1)
        normalized = normalize_distribution_name(name)
        if normalized in result:
            raise AssertionError(f"{path.name}: duplicate distribution {name!r}")
        result[normalized] = version
    if not result:
        raise AssertionError(f"{path.name}: lock must not be empty")
    return result


class RuntimeDependencyContractTests(unittest.TestCase):
    def test_runtime_lock_is_exact_and_covered_by_development_lock(self) -> None:
        runtime = parse_lock(ROOT / "requirements-runtime.lock")
        development = parse_lock(ROOT / "requirements-dev.lock")

        missing = sorted(set(runtime) - set(development))
        self.assertEqual(missing, [], f"runtime dependencies missing from dev lock: {missing}")
        mismatched = sorted(
            name
            for name in runtime.keys() & development.keys()
            if runtime[name] != development[name]
        )
        self.assertEqual(
            mismatched,
            [],
            f"runtime/dev lock version mismatch for runtime dependencies: {mismatched}",
        )

    def test_entrypoint_dependency_contract_is_current(self) -> None:
        self.assertEqual([], validate(ROOT))

    def test_missing_jsonschema_from_development_fixture_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements-dev.lock").write_text("attrs===1.0\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "tests").mkdir()
            (root / "scripts" / "entry.py").write_text(
                "from jsonschema import Draft202012Validator\n", encoding="utf-8"
            )
            environment = Environment("fixture", "requirements-dev.lock", ("scripts/entry.py",))
            errors = validate_environment(root, environment)
        self.assertTrue(any("jsonschema" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
