import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGLISH = ROOT / "docs" / "lifecycle.md"
JAPANESE = ROOT / "translations" / "ja" / "docs" / "lifecycle.md"


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class AntiStallReaderProjectionTests(unittest.TestCase):
    def test_reader_projection_explains_policy_owned_anti_stall_semantics(self) -> None:
        text = _normalized(ENGLISH)
        for required in (
            "Anti-stall repository-change behavior",
            "Policy remains the semantic authority",
            "tool activity is not material progress",
            "strategy switch",
            "invalidated path",
            "external wait",
            "diagnostic stall",
            "completion frontier",
            "next safe action",
            "does not define independent retry thresholds",
        ):
            self.assertIn(required, text)

    def test_reader_projection_marks_policy_dependencies_as_staged(self) -> None:
        text = _normalized(ENGLISH)
        for required in (
            "staged Policy candidates `#773 -> #774`",
            "contains neither staged candidate set",
            "This explanation is **staged** with Policy PRs `#773 -> #774`",
            "does not itself promote or authorize the staged Policy candidate",
        ):
            self.assertIn(required, text)

    def test_reader_projection_describes_resume_without_restarting_failed_exploration(self) -> None:
        text = _normalized(ENGLISH)
        self.assertIn("resume does not restart the investigation", text)
        self.assertIn("retry condition", text)
        self.assertIn("review-finding ledger remains authoritative", text)
        self.assertIn("does not copy finding-level disposition", text)

    def test_japanese_reference_translation_carries_the_same_boundary(self) -> None:
        text = _normalized(JAPANESE)
        for required in (
            "anti-stall repository-change behavior",
            "semantic authority は Policy が保持",
            "tool activity は material progress ではありません",
            "strategy switch",
            "invalidated path",
            "external wait",
            "diagnostic stall",
            "completion frontier",
            "next safe action",
            "独自の retry threshold",
        ):
            self.assertIn(required, text)

    def test_japanese_resume_and_finding_ledger_clauses_are_protected(self) -> None:
        text = _normalized(JAPANESE)
        self.assertIn("resume は investigation のやり直しではなく", text)
        self.assertIn("review-finding ledger remains authoritative", text)
        self.assertIn("Work ledger は finding-level disposition や closure evidence を複製しません", text)


if __name__ == "__main__":
    unittest.main()
