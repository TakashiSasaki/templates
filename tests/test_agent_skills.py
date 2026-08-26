from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
SKILLS_ROOT = ROOT / ".agents" / "skills"
EXPECTED_SKILLS = {
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
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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
            "deployment-state.json",
        ):
            with self.subTest(reference=reference):
                self.assertIn(reference, publication)
                self.assertTrue((ROOT / reference).is_file())

        for reference in ("MAINTENANCE.md", "PUBLISHING.md", ".github/workflows/"):
            with self.subTest(reference=reference):
                self.assertIn(reference, exact_head)

        self.assertIn("exactly `composition` and `policy`", publication)
        self.assertIn("exactly `composition` and `policy`", AGENTS.read_text(encoding="utf-8"))

    def test_exact_head_skill_preserves_acceptance_invariants(self) -> None:
        skill = (
            SKILLS_ROOT / "site-pr-exact-head-acceptance" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for invariant in (
            "exact head SHA",
            "base drift",
            "unresolved",
            "commit-associated",
            "Green CI on SHA A is not acceptance of SHA B",
            "Review of SHA A is not automatically review of changed SHA B",
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant.lower(), skill.lower())

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
        ):
            with self.subTest(invariant=invariant):
                self.assertIn(invariant.lower(), skill.lower())


if __name__ == "__main__":
    unittest.main()
