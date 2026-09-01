from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBAPP_OVERVIEWS = (
    ROOT / "components" / "artifact.webapp-core" / "files" / "README.md",
    ROOT / "translations" / "ja" / "components" / "artifact.webapp-core" / "files" / "README.md",
)
CURRENT_WALKTHROUGH_URL = "https://templates.moukaeritai.work/webapp/product-walkthrough/"
LEGACY_WALKTHROUGH_URL = (
    "https://templates.moukaeritai.work/composition/use/webapp-product-walkthrough/"
)


class WebappReaderEntrypointLinkTests(unittest.TestCase):
    def test_webapp_overviews_use_current_reader_walkthrough_route(self) -> None:
        for path in WEBAPP_OVERVIEWS:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn(CURRENT_WALKTHROUGH_URL, text)
                self.assertNotIn(LEGACY_WALKTHROUGH_URL, text)


if __name__ == "__main__":
    unittest.main()
