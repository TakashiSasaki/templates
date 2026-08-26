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

    def test_pending_and_stale_review_transitions_are_explicit(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "pending review",
            "is not a completed review",
            "if the pr head changes after review",
            "classify prior review evidence as stale",
            "until a new review completes for the new head",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_base_drift_requires_semantic_re_evaluation(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "if it differs from the evaluated pr base/current target snapshot",
            "must be rebuilt, rebased, or otherwise synchronized",
            "conflict-free mergeability alone does not establish semantic freshness",
            "all previous final-head ci and review evidence becomes stale",
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
            "ref visibility and actions/check indexing are not atomic",
            "a zero-result response is negative evidence, not proof",
            "enter `ci_discovery_pending` and use read-only discovery only",
            "workflow-run view",
            "exact-commit check-run/check-suite view",
            "at least two independently indexed live views",
            "remain `ci_discovery_pending`",
            "do not close and reopen the pull request",
            "create a no-op commit",
            "solely to retrigger ci while `ci_discovery_pending`",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_ci_discovery_states_are_fail_closed_and_distinct(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "may resolve only to `ci_discovered`",
            "or to `ci_confirmed_absent` after the full confirmed-absence protocol succeeds",
            "cannot transition directly to `ci_green`, `blocked_ci`, a retrigger mutation, or `merge_allowed`",
            "use `ci_confirmed_absent` only when the confirmed-absence protocol below is satisfied",
            "`ci_confirmed_absent` is not a success state",
            "must lead to `blocked_ci` or to an explicitly justified recovery action",
            "`ci_discovery_pending` != `ci_confirmed_absent`",
            "`ci_discovered` != `ci_green`",
            "`ci_confirmed_absent` is a positive evidence decision",
            "ci discovery is resolved as `ci_discovered`",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_confirmed_absence_requires_correlated_read_only_evidence(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "do not classify an expected run as `ci_confirmed_absent` from a single zero-result view",
            "repeated queries against only one index",
            "the pr head remained unchanged throughout the observation",
            "the current workflow definition still says the run should exist",
            "repeated read-only refreshes in at least two independently indexed live views",
            "no contradictory pending, queued, in-progress, or newly indexed exact-head evidence exists",
            "concrete observations that support the `ci_confirmed_absent` decision",
            "only after entering `ci_confirmed_absent` may a recovery mutation be considered",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_confirmed_absence_has_a_minimum_observation_floor(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "`ci_discovery_min_observation_minutes = 10`",
            "this minimum observation floor is a guard, not evidence",
            "it does not delay `ci_discovered` when positive exact-head evidence appears",
            "do not sleep solely to satisfy it",
            "since the later of the pr action expected to generate the run and the exact head becoming current",
            "observation-floor elapsed != `ci_confirmed_absent`",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_ci_discovery_rejects_stale_and_superseded_false_failures(self) -> None:
        skill = SKILL.read_text(encoding="utf-8").lower()
        for invariant in (
            "an older-head result is stale evidence",
            "concurrency-cancelled run that was superseded",
            "is not by itself a ci failure",
            "evaluate the newest applicable run",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_success_path_cannot_skip_ci_discovery_or_review_completion(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn(
            "PR_OPEN -> SCOPE_AUDITED -> CI_DISCOVERED -> CI_GREEN -> "
            "REVIEW_REQUESTED -> REVIEW_COMPLETED -> FINDINGS_CLEARED -> "
            "FINAL_STATE_REFRESHED -> MERGE_ALLOWED",
            skill,
        )
        self.assertIn("`SCOPE_AUDITED -> CI_GREEN` is forbidden", skill)
        self.assertIn("`CI_GREEN -> MERGE_ALLOWED` is forbidden", skill)
        self.assertIn("`REVIEW_REQUESTED -> MERGE_ALLOWED` is forbidden", skill)


if __name__ == "__main__":
    unittest.main()
