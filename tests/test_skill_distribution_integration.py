from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"
SOURCE_TREE_PAGE = ROOT / "docs/repository-trees/skill.md"
COPYABLE_TREE_PAGE = ROOT / "docs/repository-trees/skill/template.md"
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
FINAL_SKILL_REVISION = "1ee1cfd6355131746a780ea46d165e5ae1cadf50"


class SkillDistributionIntegrationTests(unittest.TestCase):
    def test_site_locks_the_final_reviewed_skill_revision(self) -> None:
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))

        self.assertEqual(
            FINAL_SKILL_REVISION,
            source_lock["publications"]["skill"]["revision"],
        )
        self.assertEqual(FINAL_SKILL_REVISION, state["locked_skill_revision"])
        self.assertRegex(FINAL_SKILL_REVISION, r"\A[0-9a-f]{40}\Z")
        self.assertEqual("active", state["status"])
        self.assertIn("skill", state["reason"])

    def test_repository_tree_pages_distinguish_source_and_distribution(self) -> None:
        source_page = SOURCE_TREE_PAGE.read_text(encoding="utf-8")
        copyable_page = COPYABLE_TREE_PAGE.read_text(encoding="utf-8")

        self.assertIn("complete template-product source artifact", source_page)
        self.assertIn("Skill copyable template tree", source_page)
        self.assertIn("GENERATED_REPOSITORY_TREE:skill", source_page)
        self.assertIn("only the tracked contents below `skill/template/`", copyable_page)
        self.assertIn("cp -a template/. /path/to/new-skill/", copyable_page)
        self.assertIn("GENERATED_SKILL_TEMPLATE_TREE", copyable_page)

    def test_build_generates_and_validates_the_skill_copyable_tree(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")

        generator = workflow.index("- name: Generate Skill copyable template tree")
        complete_trees = workflow.index("- name: Generate repository trees")
        previews = workflow.index("- name: Generate inline file previews")
        self.assertLess(complete_trees, generator)
        self.assertLess(generator, previews)
        self.assertIn(
            "python site-source/scripts/generate_skill_template_tree.py",
            workflow,
        )
        self.assertIn("--skill-root skill-source", workflow)
        self.assertIn(
            "build/site/repository-trees/skill/template/index.html",
            workflow,
        )
        self.assertIn(
            "for copyable in skill webapp; do",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
