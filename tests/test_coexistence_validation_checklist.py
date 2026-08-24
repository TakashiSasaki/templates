from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "policy-composition-coexistence.md"
JAPANESE = ROOT / "translations" / "ja" / "docs" / "policy-composition-coexistence.md"


class CoexistenceValidationChecklistTests(unittest.TestCase):
    def test_canonical_checklist_keeps_provider_validation_independent(self) -> None:
        text = CANONICAL.read_text(encoding="utf-8")
        self.assertIn("## Consumer coexistence validation checklist", text)
        self.assertIn(
            "/agent-skills/composition/scripts/run.py \\\n     --repository /path/to/repository \\\n     inspect",
            text,
        )
        self.assertIn(
            "/agent-skills/composition/scripts/run.py \\\n     --repository /path/to/repository \\\n     validate",
            text,
        )
        for command in ("validate", "render", "check"):
            self.assertIn(
                "/agent-skills/agent-policy/scripts/run.py \\\n     --repository /path/to/repository \\\n     " + command,
                text,
            )
        self.assertIn("After Policy render/finalization, run Composition `inspect` and `validate` again", text)
        self.assertIn("Policy operations must not modify `.template-composition/**`", text)
        self.assertIn(
            "Composition operations must not modify `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`",
            text,
        )
        self.assertIn("Site does not execute it on the consumer's behalf", text)
        self.assertIn("does not introduce an umbrella management command", text)

    def test_japanese_checklist_preserves_the_same_operational_boundary(self) -> None:
        text = JAPANESE.read_text(encoding="utf-8")
        self.assertIn("## Consumer 向け共存 validation checklist", text)
        self.assertIn("Composition を inspect / validate", text)
        self.assertIn("Policy を validate / render / check", text)
        self.assertIn("Composition の `inspect` と `validate` をもう一度実行", text)
        self.assertIn("Policy operation は `.template-composition/**` を変更してはならず", text)
        self.assertIn("umbrella management command を新設するものでもありません", text)


if __name__ == "__main__":
    unittest.main()
