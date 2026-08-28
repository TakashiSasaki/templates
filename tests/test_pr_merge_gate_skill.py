from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
SKILL = ROOT / ".agents" / "skills" / "pr-merge-gate" / "SKILL.md"
SOURCE = ROOT / ".agents" / "skills" / "pr-merge-gate" / "source.json"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class PullRequestMergeGateReferenceTests(unittest.TestCase):
    def test_agents_routes_merge_completion_through_reference_shim(self) -> None:
        index = AGENTS.read_text(encoding="utf-8")
        self.assertIn(".agents/skills/pr-merge-gate/SKILL.md", index)
        self.assertIn("before declaring any pull request merge-ready", index.lower())
        self.assertIn("green ci and `reviews = 0`", index.lower())

    def test_shim_has_stable_agent_skill_identity(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        _, frontmatter, body = text.split("---\n", 2)
        self.assertRegex(frontmatter, r"(?m)^name: pr-merge-gate$")
        self.assertRegex(frontmatter, r"(?m)^description: .+$")
        self.assertRegex(body.lstrip(), r"^# Pull Request Merge Gate\n")
        self.assertTrue(re.fullmatch(r"[a-z0-9-]+", SKILL.parent.name))

    def test_source_manifest_pins_immutable_policy_adapter_identity(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(source["schema_version"], 1)
        self.assertEqual(source["kind"], "policy-adapter-reference")
        self.assertEqual(source["repository"], "TakashiSasaki/templates")
        self.assertEqual(source["path"], "skills/pr-merge-gate/SKILL.md")
        self.assertRegex(source["revision"], SHA_PATTERN)
        self.assertRegex(source["blob_sha"], SHA_PATTERN)
        self.assertNotEqual(source["revision"], source["blob_sha"])

    def test_shim_declares_reference_not_policy_authority(self) -> None:
        text = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "repository-local reference shim",
            "does not define shared pull-request policy",
            "duplicate the adapter's github orchestration semantics",
            "the immutable source identity is recorded in the adjacent `source.json`",
            "current composition code, schemas, validators, tests, workflows",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, text)

    def test_shim_loads_only_exact_verified_source_and_fails_closed(self) -> None:
        text = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "use the github connector to fetch `path` from exactly `revision`",
            "returned file blob sha equals `blob_sha`",
            "do not resolve the source through a branch name",
            "full 40-character lowercase hexadecimal sha",
            "if any source field is missing, malformed, unavailable, or mismatched",
            "stop in a blocked state",
            "source unavailability is a blocked condition",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, text)

    def test_shim_does_not_duplicate_policy_adapter_mechanics(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        forbidden = (
            "CI_DISCOVERY_MIN_OBSERVATION_MINUTES",
            "CI_DISCOVERY_PENDING",
            "CI_CONFIRMED_ABSENT",
            "BLOCKED_REVIEW_MISSING",
            "BLOCKED_REVIEW_STALE",
            "PR_OPEN -> SCOPE_AUDITED",
            "expected_head_sha",
            "@hermes review",
            "check-run",
            "check-suite",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, text)

    def test_shim_keeps_composition_acceptance_separate(self) -> None:
        text = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "task-specific composition implementation, schema, runtime, release",
            "composition-specific semantic acceptance",
            "keep composition-specific acceptance evidence separate",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, text)


if __name__ == "__main__":
    unittest.main()
