from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _trigger_branches(workflow: str, event: str) -> list[str]:
    trigger = workflow.split("\njobs:\n", 1)[0]
    match = re.search(
        rf"(?ms)^  {re.escape(event)}:\n(?P<body>.*?)(?=^  [A-Za-z_]+:|\Z)",
        trigger,
    )
    if not match:
        raise AssertionError(f"missing trigger: {event}")
    branches = re.search(
        r"(?m)^    branches:\n(?P<items>(?:^      - .+\n?)+)",
        match.group("body"),
    )
    if not branches:
        raise AssertionError(f"missing branches for trigger: {event}")
    return [
        _unquote(line.split("-", 1)[1])
        for line in branches.group("items").splitlines()
    ]


class SchemaValidationCIPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_schema_validation_uses_pr_and_authoritative_push_tiers_only(self) -> None:
        self.assertEqual(_trigger_branches(self.workflow, "push"), ["composition"])
        self.assertEqual(_trigger_branches(self.workflow, "pull_request"), ["composition"])
        trigger = self.workflow.split("\njobs:\n", 1)[0]
        self.assertNotIn("agent/composition-", trigger)


if __name__ == "__main__":
    unittest.main()
