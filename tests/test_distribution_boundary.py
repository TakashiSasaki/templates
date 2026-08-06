from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = ROOT / "docs/architecture/distribution-classification.json"
IGNORED_LOCAL_ENTRIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
}


class DistributionBoundaryTests(unittest.TestCase):
    def load_classification(self) -> dict[str, object]:
        value = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_every_current_top_level_entry_has_exactly_one_class(self) -> None:
        classification = self.load_classification()["topLevelClassification"]
        self.assertEqual(
            {"distribution", "split", "maintainer"},
            set(classification),
        )

        classified: list[str] = []
        for category, entries in classification.items():
            with self.subTest(category=category):
                self.assertIsInstance(entries, list)
                self.assertEqual(sorted(entries), entries)
                self.assertEqual(len(entries), len(set(entries)))
                classified.extend(entries)

        self.assertEqual(len(classified), len(set(classified)))
        actual = sorted(
            path.name
            for path in ROOT.iterdir()
            if path.name not in IGNORED_LOCAL_ENTRIES
        )
        self.assertEqual(actual, sorted(classified))
        self.assertEqual(["template"], classification["distribution"])
        self.assertIn("distribution-manifest.json", classification["maintainer"])

    def test_copy_contract_is_literal_and_uses_safe_relative_roots(self) -> None:
        value = self.load_classification()

        self.assertEqual(1, value["schemaVersion"])
        self.assertEqual("template", value["targetDistributionRoot"])
        self.assertEqual(".", value["directCopyDestination"])
        self.assertIs(value["contentTransformationAllowed"], False)

        roots = value["targetSourceRoots"]
        self.assertEqual(
            {
                "distribution": "template",
                "maintainer": ".",
                "publicationInterface": "docs/publication-catalog.json",
            },
            roots,
        )
        for path_text in roots.values():
            path = PurePosixPath(path_text)
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertNotIn(".git", {part.lower() for part in path.parts})

    def test_required_rules_close_source_distribution_and_product_roles(self) -> None:
        rules = self.load_classification()["requiredSeparationRules"]

        self.assertIsInstance(rules, list)
        self.assertEqual(5, len(rules))
        self.assertTrue(all(isinstance(rule, str) and rule for rule in rules))
        combined = " ".join(rules).lower()
        for required_term in (
            "branch root",
            "product repository root",
            "escape template",
            "publication",
            "clean-room",
        ):
            with self.subTest(required_term=required_term):
                self.assertIn(required_term, combined)

    def test_distribution_validator_passes_both_entry_points(self) -> None:
        for command in (
            ("scripts/validate_distribution.py",),
            ("-m", "scripts.validate_distribution"),
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, *command],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    0,
                    result.returncode,
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
