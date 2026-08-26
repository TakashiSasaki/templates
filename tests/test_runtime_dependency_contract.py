from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSUMER_WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
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

    def test_clean_runtime_uses_current_revision_checkout(self) -> None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
        clean_runtime = workflow.split("\n  clean-runtime:\n", 1)[1].split(
            "\n  materialized-validation:\n", 1
        )[0]
        self.assertIn("name: Check out current Composition revision", clean_runtime)
        self.assertIn("fetch-depth: 1", clean_runtime)
        self.assertNotIn("fetch-depth: 0", clean_runtime)


if __name__ == "__main__":
    unittest.main()
