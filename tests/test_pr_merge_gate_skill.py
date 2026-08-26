from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
SKILL = ROOT / ".agents" / "skills" / "pr-merge-gate" / "SKILL.md"


class PullRequestMergeGateSkillTests(unittest.TestCase):
    def test_agents_routes_all_merge_completion_through_merge_gate(self) -> None:
        index = AGENTS.read_text(encoding="utf-8")
        self.assertIn(".agents/skills/pr-merge-gate/SKILL.md", index)
        self.assertIn("before declaring any pull request merge-ready", index.lower())
        self.assertIn("green ci and `reviews = 0`", index.lower())

    def test_skill_frontmatter_and_name_are_stable(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        _, frontmatter, body = text.split("---\n", 2)
        self.assertRegex(frontmatter, r"(?m)^name: pr-merge-gate$")
        self.assertRegex(frontmatter, r"(?m)^description: .+$")
        self.assertRegex(body.lstrip(), r"^# Pull Request Merge Gate\n")
        self.assertTrue(re.fullmatch(r"[a-z0-9-]+", SKILL.parent.name))

    def test_zero_pending_stale_and_self_review_fail_closed(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "`reviews = 0 -> merge_allowed` is forbidden",
            "completed independent review evidence count is zero",
            "self-review does not satisfy this requirement",
            "reviewer unavailable != review waived",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_all_blocked_states_are_defined(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for state in (
            "blocked_ci",
            "blocked_review_missing",
            "blocked_review_pending",
            "blocked_review_stale",
            "blocked_review_findings",
            "blocked_base_drift",
            "blocked_head_changed",
            "blocked_mergeability",
        ):
            with self.subTest(state=state):
                self.assertIn(state, skill)

    def test_exact_head_and_final_live_refresh_are_mandatory(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "final live-state refresh",
            "review of sha a != review of changed sha b",
            "expected_head_sha",
            "never omit `expected_head_sha`",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_ci_discovery_lag_cannot_trigger_mutating_retry(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "workflow/check discovery may lag",
            "refresh workflow runs and check state for that exact commit",
            "do not close and reopen the pull request",
            "create a no-op commit",
            "solely to retrigger ci",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_success_path_cannot_skip_review_completion(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn(
            "PR_OPEN -> SCOPE_AUDITED -> CI_GREEN -> REVIEW_REQUESTED -> "
            "REVIEW_COMPLETED -> FINDINGS_CLEARED -> FINAL_STATE_REFRESHED -> "
            "MERGE_ALLOWED",
            skill,
        )
        self.assertIn("`CI_GREEN -> MERGE_ALLOWED` is forbidden", skill)
        self.assertIn("`REVIEW_REQUESTED -> MERGE_ALLOWED` is forbidden", skill)


if __name__ == "__main__":
    unittest.main()
