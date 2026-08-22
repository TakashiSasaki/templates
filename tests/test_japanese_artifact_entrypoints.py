from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from scripts.translation_link_selection import rewrite_current_localized_links


ROOT = Path(__file__).resolve().parents[1]
LANDING_TRANSLATION = ROOT / "translations" / "ja" / "docs" / "landing.md"


@dataclass(frozen=True)
class RouteRecord:
    language: str
    canonical_destination: PurePosixPath
    translation_destination: PurePosixPath


class JapaneseArtifactEntrypointTests(unittest.TestCase):
    def test_skill_and_webapp_entrypoints_localize_without_deep_route_guessing(self) -> None:
        source_text = LANDING_TRANSLATION.read_text(encoding="utf-8")
        self.assertIn('href="/skill/"', source_text)
        self.assertIn('href="/webapp/"', source_text)
        self.assertNotIn('href="/ja/skill/"', source_text)
        self.assertNotIn('href="/ja/webapp/"', source_text)

        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary) / "docs"
            landing = docs / "ja" / "index.md"
            skill = docs / "ja" / "skill" / "index.md"
            webapp = docs / "ja" / "webapp" / "index.md"
            skill.parent.mkdir(parents=True)
            webapp.parent.mkdir(parents=True)
            landing.parent.mkdir(parents=True, exist_ok=True)
            landing.write_text(
                source_text
                + "\n[Skill contract](/skill/SKILL/)\n"
                + "[Webapp contract](/webapp/docs/)\n",
                encoding="utf-8",
            )
            skill.write_text("# Skill JA\n", encoding="utf-8")
            webapp.write_text("# Webapp JA\n", encoding="utf-8")

            records = [
                RouteRecord("ja", PurePosixPath("index.md"), PurePosixPath("ja/index.md")),
                RouteRecord(
                    "ja",
                    PurePosixPath("skill/index.md"),
                    PurePosixPath("ja/skill/index.md"),
                ),
                RouteRecord(
                    "ja",
                    PurePosixPath("webapp/index.md"),
                    PurePosixPath("ja/webapp/index.md"),
                ),
            ]

            rewrite_current_localized_links(records, docs)
            rendered = landing.read_text(encoding="utf-8")

            self.assertIn('href="/ja/skill/"', rendered)
            self.assertIn('href="/ja/webapp/"', rendered)
            self.assertIn("[Skill contract](/skill/SKILL/)", rendered)
            self.assertIn("[Webapp contract](/webapp/docs/)", rendered)


if __name__ == "__main__":
    unittest.main()
