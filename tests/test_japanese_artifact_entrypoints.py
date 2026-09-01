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
    def test_selector_and_downstream_artifact_routes_localize_without_deep_route_guessing(self) -> None:
        source_text = LANDING_TRANSLATION.read_text(encoding="utf-8")
        for route in (
            "/web/",
            "/website/",
            "/webapp/",
            "/composition/use/skill-first-use-walkthrough/",
        ):
            with self.subTest(route=route):
                self.assertIn(f'href="{route}"', source_text)
                self.assertNotIn(f'href="/ja{route}"', source_text)
        self.assertNotIn(
            'href="/composition/use/webapp-product-walkthrough/"',
            source_text,
        )

        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary) / "docs"
            landing = docs / "ja" / "index.md"
            localized = {
                "web": docs / "ja" / "web" / "index.md",
                "website": docs / "ja" / "website" / "index.md",
                "webapp": docs / "ja" / "webapp" / "index.md",
                "skill": (
                    docs
                    / "ja"
                    / "composition"
                    / "use"
                    / "skill-first-use-walkthrough.md"
                ),
            }
            landing.parent.mkdir(parents=True, exist_ok=True)
            landing.write_text(
                source_text
                + "\n[Skill contract](/skill/SKILL/)\n"
                + "[Webapp reference](/webapp/docs/)\n",
                encoding="utf-8",
            )
            for path in localized.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# localized\n", encoding="utf-8")

            records = [
                RouteRecord("ja", PurePosixPath("index.md"), PurePosixPath("ja/index.md")),
                RouteRecord(
                    "ja",
                    PurePosixPath("web/index.md"),
                    PurePosixPath("ja/web/index.md"),
                ),
                RouteRecord(
                    "ja",
                    PurePosixPath("website/index.md"),
                    PurePosixPath("ja/website/index.md"),
                ),
                RouteRecord(
                    "ja",
                    PurePosixPath("webapp/index.md"),
                    PurePosixPath("ja/webapp/index.md"),
                ),
                RouteRecord(
                    "ja",
                    PurePosixPath("composition/use/skill-first-use-walkthrough.md"),
                    PurePosixPath("ja/composition/use/skill-first-use-walkthrough.md"),
                ),
            ]

            rewrite_current_localized_links(records, docs)
            rendered = landing.read_text(encoding="utf-8")

            for route in (
                "/ja/web/",
                "/ja/website/",
                "/ja/webapp/",
                "/ja/composition/use/skill-first-use-walkthrough/",
            ):
                with self.subTest(route=route):
                    self.assertIn(f'href="{route}"', rendered)
            self.assertIn("[Skill contract](/skill/SKILL/)", rendered)
            self.assertIn("[Webapp reference](/webapp/docs/)", rendered)


if __name__ == "__main__":
    unittest.main()
