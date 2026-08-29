from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


class RepositoryBrowserFilterContractTests(unittest.TestCase):
    def test_filter_uses_only_static_repository_paths(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('tree.querySelectorAll("a[data-repository-file]")', controller)
        self.assertIn("link.dataset.filePath", controller)
        self.assertIn("path.toLocaleLowerCase()", controller)
        self.assertNotIn("fetch(", controller)
        self.assertNotIn("XMLHttpRequest", controller)

    def test_keyboard_contract_is_explicit_and_bounded(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('event.key === "Escape"', controller)
        self.assertIn('event.key === "Enter"', controller)
        self.assertIn('event.key !== "/"', controller)
        self.assertIn("targetIsEditable", controller)
        self.assertNotIn("touchstart", controller)
        self.assertNotIn("touchmove", controller)


if __name__ == "__main__":
    unittest.main()
