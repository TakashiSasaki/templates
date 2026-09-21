"""Documentation-discovery checks, not proof of agent or workflow correctness.

The semantic content needs review. These tests keep the source-only guide
reachable without silently promoting it into published or generated policy.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("docs/agent-task-design.md", "docs/agent-task-briefs.md")


class AgentTaskGuidanceTests(unittest.TestCase):
    def test_root_navigation_reaches_every_page(self) -> None:
        index = (ROOT / "index.md").read_text(encoding="utf-8")
        for page in PAGES:
            with self.subTest(page=page):
                self.assertTrue((ROOT / page).is_file())
                self.assertIn(f"]({page})", index)

    def test_discovery_declares_source_only_ownership(self) -> None:
        config = json.loads((ROOT / ".progressive-discovery.json").read_text(encoding="utf-8"))
        self.assertEqual(len(config["expected_documents"]), len(set(config["expected_documents"])))
        for page in PAGES:
            with self.subTest(page=page):
                self.assertIn(page, config["expected_documents"])
                self.assertIn(page, config["surface_boundaries"]["provider-maintenance"])
                self.assertTrue(config["authored_index_exclusions"]["docs/index.md"].get(page))
                self.assertNotIn(page, config["surface_boundaries"]["generated"])
                self.assertNotIn(page, config["surface_boundaries"]["consumer-distributed"])

    def test_pages_have_one_title_and_no_conflict_markers(self) -> None:
        for page in PAGES:
            with self.subTest(page=page):
                text = (ROOT / page).read_text(encoding="utf-8")
                # Ignore fenced prompt examples: their headings are payload.
                prose = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.M | re.S)
                self.assertEqual(len(re.findall(r"^# [^#]", prose, re.M)), 1)
                self.assertIsNone(re.search(r"^(?:<<<<<<<|=======|>>>>>>>)", text, re.M))
                self.assertTrue(text.endswith("\n"))

    def test_guide_retains_its_navigation_sections(self) -> None:
        text = (ROOT / "docs/agent-task-design.md").read_text(encoding="utf-8")
        required = (
            "Design premise",
            "Existing authority, not another rule set",
            "Choose preparation proportional to uncertainty",
            "Prepare a compact design packet",
            "Test claims, not convenient proxies",
            "Use formal models where they resolve a concrete design risk",
            "Write instructions that preserve judgment and reduce memory burden",
            "Respond to reviews without turning review into the specification author",
            "Budgets, handoff, and gradual improvement",
            "Historical motivation, not runtime authority",
        )
        headings = re.findall(r"^## (.+)$", text, re.M)
        self.assertEqual(len(headings), len(set(headings)))
        for heading in required:
            self.assertIn(heading, headings)


    def test_templates_have_unambiguous_copy_boundaries(self) -> None:
        text = (ROOT / "docs/agent-task-briefs.md").read_text(encoding="utf-8")
        for name in ("GOAL", "TASK BRIEF", "STEERING"):
            with self.subTest(template=name):
                begin, end = f"<!-- BEGIN {name} TEMPLATE -->", f"<!-- END {name} TEMPLATE -->"
                self.assertEqual(text.count(begin), 1)
                self.assertEqual(text.count(end), 1)
                self.assertLess(text.index(begin), text.index(end))
                block = text.split(begin, 1)[1].split(end, 1)[0].strip()
                self.assertTrue(block.startswith("```text\n"))
                self.assertTrue(block.endswith("\n```"))

    def test_expanded_brief_keeps_required_fields(self) -> None:
        text = (ROOT / "docs/agent-task-briefs.md").read_text(encoding="utf-8")
        block = text.split("<!-- BEGIN TASK BRIEF TEMPLATE -->", 1)[1].split(
            "<!-- END TASK BRIEF TEMPLATE -->", 1
        )[0]
        for heading in (
            "Outcome and completion", "Authority and scope", "Assumptions and observations",
            "Acceptance obligations", "Design and implementation", "Validation and review",
            "Budget and stop", "Handoff",
        ):
            self.assertIn(f"## {heading}\n", block)

    def test_templates_link_to_the_method(self) -> None:
        brief = (ROOT / "docs/agent-task-briefs.md").read_text(encoding="utf-8")
        self.assertIn("](agent-task-design.md)", brief)

if __name__ == "__main__":
    unittest.main()
