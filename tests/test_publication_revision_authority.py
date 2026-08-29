from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
CUTOVER_SKILL = ROOT / ".agents/skills/site-publication-cutover/SKILL.md"
OBSOLETE_DEPLOYMENT_STATE = ROOT / "deployment-state.json"
FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")


class PublicationRevisionAuthorityTests(unittest.TestCase):
    def test_publication_sources_owns_current_provider_revisions(self) -> None:
        lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(set(lock["publications"]), {"composition", "policy"})
        for provider in ("composition", "policy"):
            with self.subTest(provider=provider):
                revision = lock["publications"][provider]["revision"]
                self.assertIsNotNone(FULL_SHA.fullmatch(revision))

    def test_completed_migration_state_is_not_an_active_revision_authority(self) -> None:
        self.assertFalse(OBSOLETE_DEPLOYMENT_STATE.exists())
        skill = CUTOVER_SKILL.read_text(encoding="utf-8")
        self.assertIn("sole committed authority", skill)
        self.assertNotIn("deployment-state.json", skill)


if __name__ == "__main__":
    unittest.main()
