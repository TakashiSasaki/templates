from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "getting-started.md"


class GettingStartedMigrationSequenceTests(unittest.TestCase):
    def test_policy_edits_are_followed_by_preview_refresh_before_finalize(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        migration = text.split(
            "## 2B. Prepare migration adoption while preserving existing instructions",
            1,
        )[1].split("## 3. Operate a managed repository", 1)[0]

        policy_edit = migration.index("Represent the semantics of the handwritten instructions")
        preview = migration.index("adopt preview", policy_edit)
        stale = migration.index("STALE_OUTPUT", preview)
        finalize = migration.index("adopt finalize", stale)

        self.assertLess(policy_edit, preview)
        self.assertLess(preview, stale)
        self.assertLess(stale, finalize)
        self.assertIn("After every such Policy edit", migration)
        self.assertIn("deliberately rejects a stale preview", migration)


if __name__ == "__main__":
    unittest.main()
