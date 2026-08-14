from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "skill": "3af9540a03005fba53757d44a0b4be2bbffc9332",
    "policy": "646e75d33f1bddc5a89669468c1cff5e731c311d",
    "webapp": "ef35bebb008406370219418dd862ad8f4b1695f4",
}


class GuidedTranslationProviderLockTests(unittest.TestCase):
    def test_publication_sources_pin_reviewed_guided_translation_revisions(self) -> None:
        lock = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {name: lock["publications"][name]["revision"] for name in EXPECTED},
            EXPECTED,
        )

    def test_deployment_state_tracks_current_reviewed_skill_revision(self) -> None:
        state = json.loads(
            (ROOT / "deployment-state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["locked_skill_revision"], EXPECTED["skill"])


if __name__ == "__main__":
    unittest.main()
