from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.generate_repository_browser import BRANCH_ORDER, generate_browser


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


def run_git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout.strip()


class RepositoryBrowserMobileTests(unittest.TestCase):
    def make_repository(self, root: Path) -> None:
        root.mkdir()
        run_git(root, "init", "--quiet")
        run_git(root, "config", "user.email", "tests@example.invalid")
        run_git(root, "config", "user.name", "Repository browser mobile tests")
        (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / 'foo&bar<baz>"quote\'.py').write_text(
            "value = 1\n",
            encoding="utf-8",
        )
        run_git(root, "add", ".")
        run_git(root, "commit", "--quiet", "--message", "fixture")

    def test_generated_browser_supports_progressive_full_height_mobile_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)

            generate_browser(
                "TakashiSasaki/templates",
                output,
                {branch: repository for branch in BRANCH_ORDER},
            )

            page = (output / "files/site/index.html").read_text(encoding="utf-8")
            self.assertIn(
                "grid-template-rows: minmax(16rem, 42vh) 58vh",
                page,
            )
            self.assertIn("repository-browser-enhanced", page)
            self.assertIn("height: 100dvh", page)
            self.assertIn('data-mobile-view="files"', page)
            self.assertIn("data-repository-tree", page)
            self.assertIn("data-repository-content", page)
            self.assertIn("data-show-files", page)
            self.assertIn("data-selected-file", page)
            self.assertIn('data-file-path="README.md"', page)
            self.assertIn('script-src \'self\'', page)
            self.assertIn(
                '<script src="../repository-browser.js" defer></script>',
                page,
            )
            self.assertEqual(page.count("<script"), 1)

            copied_controller = output / "files/repository-browser.js"
            self.assertTrue(copied_controller.is_file())
            self.assertEqual(
                copied_controller.read_text(encoding="utf-8"),
                CONTROLLER.read_text(encoding="utf-8"),
            )

    def test_tree_file_metadata_escapes_special_filename_characters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            output = root / "site"
            output.mkdir()
            self.make_repository(repository)

            generate_browser(
                "TakashiSasaki/templates",
                output,
                {branch: repository for branch in BRANCH_ORDER},
            )

            page = (output / "files/site/index.html").read_text(encoding="utf-8")
            self.assertIn(
                'data-file-path="src/foo&amp;bar&lt;baz&gt;&quot;quote&#x27;.py"',
                page,
            )
            self.assertIn(
                '<code>foo&amp;bar&lt;baz&gt;"quote\'.py</code>',
                page,
            )
            self.assertNotIn(
                'data-file-path="src/foo&bar<baz>"quote\'.py"',
                page,
            )

    def test_controller_uses_explicit_navigation_without_swipe_or_history(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('matchMedia("(max-width: 800px)")', controller)
        self.assertIn('setMobileMode("content")', controller)
        self.assertIn('setMobileMode("files")', controller)
        self.assertIn("tree.inert", controller)
        self.assertIn("content.inert", controller)
        self.assertIn("preventScroll: true", controller)
        self.assertNotIn("touchstart", controller)
        self.assertNotIn("touchmove", controller)
        self.assertNotIn("pushState", controller)
        self.assertNotIn("popstate", controller)

    def test_legacy_viewport_listener_executes_and_preserves_mobile_context(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is required to execute the repository browser controller")

        harness = r"""
const fs = require("fs");
const vm = require("vm");

class Element {}
class HTMLElement extends Element {
  constructor() {
    super();
    this.dataset = {};
    this.inert = false;
    this.textContent = "";
    this.focusCount = 0;
  }
  focus() { this.focusCount += 1; }
}
class HTMLButtonElement extends HTMLElement {}
class HTMLAnchorElement extends HTMLElement {
  constructor() {
    super();
    this.attributes = new Map();
  }
  closest(selector) {
    return selector === "a[data-repository-file]" ? this : null;
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { this.attributes.delete(name); }
}

global.Element = Element;
global.HTMLElement = HTMLElement;
global.HTMLButtonElement = HTMLButtonElement;
global.HTMLAnchorElement = HTMLAnchorElement;

const tree = new HTMLElement();
const content = new HTMLElement();
const filesButton = new HTMLButtonElement();
const selectedFileLabel = new HTMLElement();
const browserHandlers = {};
const buttonHandlers = {};
const browser = new HTMLElement();
browser.dataset.mobileView = "files";
browser.querySelector = (selector) => ({
  "[data-repository-tree]": tree,
  "[data-repository-content]": content,
  "[data-show-files]": filesButton,
  "[data-selected-file]": selectedFileLabel,
})[selector] || null;
browser.addEventListener = (type, callback) => { browserHandlers[type] = callback; };
browser.contains = () => true;
filesButton.addEventListener = (type, callback) => { buttonHandlers[type] = callback; };

global.document = {
  querySelector: () => browser,
  documentElement: { classList: { add() {} } },
};

let legacyListener = null;
const mobileViewport = {
  matches: false,
  addListener(callback) { legacyListener = callback; },
};
global.window = {
  matchMedia: () => mobileViewport,
  requestAnimationFrame: (callback) => callback(),
};

vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {
  filename: process.argv[1],
});
if (typeof legacyListener !== "function") {
  throw new Error("legacy MediaQueryList listener was not registered");
}

mobileViewport.matches = true;
legacyListener({ matches: true });
const initialMobile = {
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
};

const link = new HTMLAnchorElement();
link.dataset.filePath = "README.md";
link.textContent = "README.md";
browserHandlers.click({ target: link });
const selectedMobile = {
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
};

mobileViewport.matches = false;
legacyListener({ matches: false });
const desktop = {
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
};

mobileViewport.matches = true;
legacyListener({ matches: true });
const restoredMobile = {
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
};

buttonHandlers.click();
const returnedFiles = {
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
  selectedFocusCount: link.focusCount,
};

process.stdout.write(JSON.stringify({
  initialMobile,
  selectedMobile,
  desktop,
  restoredMobile,
  returnedFiles,
}));
"""
        process = subprocess.run(
            [node, "-e", harness, str(CONTROLLER)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result = json.loads(process.stdout)
        self.assertEqual(
            result["initialMobile"],
            {"mode": "files", "treeInert": False, "contentInert": True},
        )
        self.assertEqual(
            result["selectedMobile"],
            {"mode": "content", "treeInert": True, "contentInert": False},
        )
        self.assertEqual(
            result["desktop"],
            {"mode": "content", "treeInert": False, "contentInert": False},
        )
        self.assertEqual(
            result["restoredMobile"],
            {"mode": "content", "treeInert": True, "contentInert": False},
        )
        self.assertEqual(result["returnedFiles"]["mode"], "files")
        self.assertFalse(result["returnedFiles"]["treeInert"])
        self.assertTrue(result["returnedFiles"]["contentInert"])
        self.assertEqual(result["returnedFiles"]["selectedFocusCount"], 1)


if __name__ == "__main__":
    unittest.main()
