from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "getting-started.md"


class GettingStartedMigrationSequenceTests(unittest.TestCase):
    def test_policy_edits_are_followed_by_preview_refresh_before_finalize(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        migration = text.split("## 4B. Migration adoption", 1)[1].split(
            "## 5. Choose the baseline profile and edit human-owned Policy input",
            1,
        )[0]

        policy_edit = migration.index("You must represent their intended semantics")
        preview = migration.index("adopt preview", policy_edit)
        stale = migration.index("STALE_OUTPUT", preview)
        finalize = migration.index("adopt finalize", stale)

        self.assertLess(policy_edit, preview)
        self.assertLess(preview, stale)
        self.assertLess(stale, finalize)
        self.assertIn("After changing human-owned Policy input", migration)
        self.assertIn("rejects a stale preview", migration)


if __name__ == "__main__":
    unittest.main()
