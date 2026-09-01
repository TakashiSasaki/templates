from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "translations" / "ja" / "docs" / "index.md"
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class JapaneseDocumentationIndexLinkTests(unittest.TestCase):
    def test_all_relative_links_resolve_inside_the_repository(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            target = raw.split("#", 1)[0].split("?", 1)[0]
            if not target or "://" in target or target.startswith("/"):
                continue
            resolved = (INDEX.parent / unquote(target)).resolve()
            with self.subTest(target=target):
                self.assertTrue(resolved.is_file() or resolved.is_dir(), resolved)
                self.assertTrue(resolved.is_relative_to(ROOT), resolved)

    def test_component_links_escape_the_translation_tree(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        self.assertNotIn("](../components/", text)
        for expected in (
            "](../../../components/foundation.web/",
            "](../../../components/artifact.website-core/",
            "](../../../components/artifact.webapp-core/",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
