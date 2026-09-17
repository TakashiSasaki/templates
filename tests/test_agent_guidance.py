"""Ensure intake guidance points to the executable qualification path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AgentGuidanceTests(unittest.TestCase):
    def test_skill_contract_and_commands(self):
        skill = (ROOT / ".agents/skills/register-information-model/SKILL.md").read_text()
        self.assertTrue(skill.startswith("---\nname: register-information-model\n"))
        for text in ("AUTHORITY.md", "AGENTS.md", "docs/intake.md", "python tools/qualify.py",
                     "metadata-observed", "reference-not-verified", "observedOn: null", "reference-only"):
            self.assertIn(text, skill)

    def test_guidance_links_existing_contracts(self):
        for relative in ("docs/record-model.md", "docs/source-policy.md", "docs/intake.md",
                         "schemas/resource-record-0.1.schema.json", "tools/qualify.py"):
            self.assertTrue((ROOT / relative).is_file(), relative)
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertIn(".agents/skills/register-information-model/SKILL.md", agents)
        self.assertIn("python tools/qualify.py", agents)

    def test_limits_and_language_are_explicit(self):
        text = (ROOT / "docs/intake.md").read_text()
        for item in ("canonical Japanese", "HTTP(S)", "not a claim", "Integration qualification",
                     "separate authorization", "snapshot", "negative tests"):
            self.assertIn(item, text)


if __name__ == "__main__":
    unittest.main()
