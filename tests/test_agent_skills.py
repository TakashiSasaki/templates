from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
SKILLS_ROOT = ROOT / ".agents" / "skills"
MERGE_GATE = SKILLS_ROOT / "pr-merge-gate" / "SKILL.md"
MERGE_GATE_SOURCE = SKILLS_ROOT / "pr-merge-gate" / "source.json"
EXPECTED_SKILLS = {
    "pr-merge-gate",
    "site-browser-regression-triage",
    "site-publication-cutover",
    "site-pr-exact-head-acceptance",
}
REQUIRED_SECTIONS = (
    "## Purpose",
    "## Use when",
    "## Do not use when",
    "## Canonical authorities",
    "## Inputs",
    "## Stop conditions",
    "## Evidence to report",
)
BROWSER_CHECK_SCRIPTS = (
    "scripts/check_mobile_layout.py",
    "scripts/check_glossary_locale_chrome.py",
    "scripts/check_pwa_freshness.py",
    "scripts/check_pwa_locale_chrome.py",
    "scripts/check_pwa_commit_regressions.py",
    "scripts/check_pwa_slow_convergence.py",
    "scripts/check_pwa_capabilities.py",
    "scripts/check_search_history.py",
    "scripts/check_search_history_review_regressions.py",
)
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def load_skill(path: Path) -> tuple[dict[str, object], str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} must start with YAML frontmatter")
    try:
        _, frontmatter, body = text.split("---\n", 2)
    except ValueError as exc:
        raise AssertionError(f"{path} has unterminated YAML frontmatter") from exc
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise AssertionError(f"{path} frontmatter must be a mapping")
    return metadata, body, text


class AgentSkillContractTests(unittest.TestCase):
    def test_agents_index_routes_to_expected_repo_local_skills(self) -> None:
        index = AGENTS.read_text(encoding="utf-8")
        for skill_name in EXPECTED_SKILLS:
            with self.subTest(skill=skill_name):
                skill_file = SKILLS_ROOT / skill_name / "SKILL.md"
                self.assertTrue(skill_file.is_file())
                self.assertIn(
                    f".agents/skills/{skill_name}/SKILL.md",
                    index,
                )

    def test_all_repo_local_skills_follow_agent_skills_frontmatter_contract(self) -> None:
        skill_files = sorted(SKILLS_ROOT.glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skill_files), len(EXPECTED_SKILLS))

        descriptions: set[str] = set()
        for skill_file in skill_files:
            metadata, body, _ = load_skill(skill_file)
            skill_name = skill_file.parent.name
            with self.subTest(skill=skill_name):
                self.assertEqual(metadata.get("name"), skill_name)
                self.assertRegex(skill_name, NAME_PATTERN)
                self.assertLessEqual(len(skill_name), 64)

                description = metadata.get("description")
                self.assertIsInstance(description, str)
                assert isinstance(description, str)
                self.assertTrue(description.strip())
                self.assertLessEqual(len(description), 1024)
                self.assertNotIn(description, descriptions)
                descriptions.add(description)

                self.assertRegex(body.lstrip(), r"^# .+\n")
                for heading in REQUIRED_SECTIONS:
                    self.assertIn(heading, body)

    def test_skills_reference_current_canonical_site_authorities(self) -> None:
        publication = (
            SKILLS_ROOT / "site-publication-cutover" / "SKILL.md"
        ).read_text(encoding="utf-8")
        exact_head = (
            SKILLS_ROOT / "site-pr-exact-head-acceptance" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for reference in (
            "MAINTENANCE.md",
            "PUBLISHING.md",
            "publication-sources.json",
            "site-manifest.json",
        ):
            with self.subTest(reference=reference):
                self.assertIn(reference, publication)
                self.assertTrue((ROOT / reference).is_file())

        self.assertNotIn("deployment-state.json", publication)

        for reference in ("MAINTENANCE.md", "PUBLISHING.md", ".github/workflows/"):
            with self.subTest(reference=reference):
                self.assertIn(reference, exact_head)

        self.assertIn("exactly `composition` and `policy`", publication)
        self.assertIn(
            "exactly `composition` and `policy`",
            AGENTS.read_text(encoding="utf-8"),
        )

    def test_site_acceptance_hands_final_merge_authorization_to_merge_gate(self) -> None:
        index = AGENTS.read_text(encoding="utf-8")
        skill = (
            SKILLS_ROOT / "site-pr-exact-head-acceptance" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for invariant in (
            "SITE_ACCEPTANCE_READY_FOR_MERGE_GATE",
            "This skill does not authorize merge",
            ".agents/skills/pr-merge-gate/SKILL.md",
            "Never report final merge readiness from this skill",
            "Green CI on SHA A is not acceptance of SHA B",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant.lower(), skill.lower())
        self.assertIn(
            "task-specific work -> `site-pr-exact-head-acceptance` -> `pr-merge-gate`",
            index,
        )
        self.assertIn("Final merge authorization for every Site pull request", index)
        self.assertIn("reviews = 0", index)

    def test_site_acceptance_handoff_reuses_valid_site_evidence(self) -> None:
        skill = (
            SKILLS_ROOT / "site-pr-exact-head-acceptance" / "SKILL.md"
        ).read_text(encoding="utf-8").lower()
        for invariant in (
            "site handoff snapshot",
            "do not discard the entire snapshot when only one binding changes",
            "do not repeat discovery merely to make a still-valid result newer",
            "do not automatically rerun unrelated diagnostics",
            "target movement also does not by itself require a new proposed head",
            "do not unconditionally reacquire the effective diff",
            "elapsed time alone does not make exact-head site evidence stale",
            "reuse the site-specific scope and ci evidence from the handoff snapshot",
            "must not unconditionally reacquire site-specific evidence",
            "diagnostic work does not become a mandatory acceptance condition",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_merge_gate_source_pins_immutable_policy_adapter_identity(self) -> None:
        source = json.loads(MERGE_GATE_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(source["schema_version"], 1)
        self.assertEqual(source["kind"], "policy-adapter-reference")
        self.assertEqual(source["repository"], "TakashiSasaki/templates")
        self.assertEqual(source["path"], "skills/pr-merge-gate/SKILL.md")
        self.assertRegex(source["revision"], SHA_PATTERN)
        self.assertRegex(source["blob_sha"], SHA_PATTERN)
        self.assertNotEqual(source["revision"], source["blob_sha"])

    def test_merge_gate_shim_declares_reference_not_policy_authority(self) -> None:
        skill = MERGE_GATE.read_text(encoding="utf-8").lower()
        for invariant in (
            "repository-local reference shim",
            "does not define shared pull-request policy",
            "duplicate the adapter's github orchestration semantics",
            "immutable source identity is recorded in the adjacent `source.json`",
            "current site code, tests, workflows, `maintenance.md`, `publishing.md`",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_merge_gate_shim_loads_only_exact_verified_source(self) -> None:
        skill = MERGE_GATE.read_text(encoding="utf-8").lower()
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
                self.assertIn(invariant, skill)

    def test_merge_gate_shim_does_not_duplicate_adapter_mechanics(self) -> None:
        skill = MERGE_GATE.read_text(encoding="utf-8")
        forbidden = (
            "CI_DISCOVERY_MIN_OBSERVATION_MINUTES",
            "CI_DISCOVERY_PENDING",
            "CI_CONFIRMED_ABSENT",
            "BLOCKED_REVIEW_MISSING",
            "BLOCKED_REVIEW_STALE",
            "PR_OPEN -> SCOPE_AUDITED",
            "expected_head_sha",
            "check-run",
            "check-suite",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, skill)

    def test_merge_gate_shim_keeps_site_acceptance_separate(self) -> None:
        skill = MERGE_GATE.read_text(encoding="utf-8").lower()
        for invariant in (
            "site-specific scope, browser/pwa, publication, provider-lock, deployment",
            "site-specific semantic acceptance",
            "keep site-specific acceptance evidence separate",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant, skill)

    def test_publication_skill_requires_exact_reviewed_provider_identity(self) -> None:
        skill = (
            SKILLS_ROOT / "site-publication-cutover" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for invariant in (
            "full 40-character lowercase provider SHA",
            "provider diff",
            "generated provenance",
            "Do not infer the target SHA from a branch name",
            "Do not expose uncataloged provider files",
            "site-pr-exact-head-acceptance` and `pr-merge-gate",
            "sole committed authority",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant.lower(), skill.lower())

    def test_browser_triage_skill_tracks_current_same_artifact_checkers(self) -> None:
        skill = (
            SKILLS_ROOT / "site-browser-regression-triage" / "SKILL.md"
        ).read_text(encoding="utf-8")
        workflow_path = ROOT / ".github" / "workflows" / "build-pages.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn(".github/workflows/build-pages.yml", skill)
        self.assertTrue(workflow_path.is_file())
        self.assertIn("FRESHNESS.md", skill)
        self.assertTrue((ROOT / "FRESHNESS.md").is_file())

        for script in BROWSER_CHECK_SCRIPTS:
            with self.subTest(script=script):
                self.assertIn(script, skill)
                self.assertTrue((ROOT / script).is_file())
                self.assertIn(script, workflow)

        for invariant in (
            "exact Pages artifact",
            "do not rebuild a different artifact",
            "source -> generated artifact -> browser runtime",
            "open Shadow Root",
            "Increase a timeout only if",
            "preflight mismatch",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant.lower(), skill.lower())


if __name__ == "__main__":
    unittest.main()
