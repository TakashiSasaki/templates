from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.generate_repository_browser as repository_browser
from scripts.generate_repository_browser import (
    BRANCH_ORDER,
    RepositoryBrowserError,
    generate_browser,
    write_browser_controller,
)


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

    def test_write_browser_controller_rejects_invalid_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            missing = root / "missing.js"
            with mock.patch.object(repository_browser, "CONTROLLER_SOURCE", missing):
                with self.assertRaisesRegex(
                    RepositoryBrowserError,
                    "controller is unavailable",
                ):
                    write_browser_controller(root)

            target = root / "target.js"
            target.write_text("(() => {})();\n", encoding="utf-8")
            symlink = root / "controller-link.js"
            symlink.symlink_to(target)
            with mock.patch.object(repository_browser, "CONTROLLER_SOURCE", symlink):
                with self.assertRaisesRegex(
                    RepositoryBrowserError,
                    "controller is unavailable",
                ):
                    write_browser_controller(root)

            nul_source = root / "nul.js"
            nul_source.write_bytes(b"before\x00after")
            with mock.patch.object(repository_browser, "CONTROLLER_SOURCE", nul_source):
                with self.assertRaisesRegex(
                    RepositoryBrowserError,
                    "controller contains NUL",
                ):
                    write_browser_controller(root)

    def test_controller_uses_explicit_navigation_with_file_history(self) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('matchMedia("(max-width: 800px)")', controller)
        self.assertIn('setMobileMode("content")', controller)
        self.assertIn('setMobileMode("files")', controller)
        self.assertIn("tree.inert", controller)
        self.assertIn("content.inert", controller)
        self.assertIn("event.defaultPrevented", controller)
        self.assertIn("event.button !== 0", controller)
        self.assertIn("event.metaKey", controller)
        self.assertIn("event.ctrlKey", controller)
        self.assertIn("event.shiftKey", controller)
        self.assertIn("event.altKey", controller)
        self.assertIn("preventScroll: true", controller)
        self.assertIn("new URLSearchParams", controller)
        self.assertIn("history.pushState", controller)
        self.assertIn('addEventListener("popstate"', controller)
        self.assertIn('addEventListener("hashchange"', controller)
        self.assertNotIn("touchstart", controller)
        self.assertNotIn("touchmove", controller)

    def test_legacy_listener_keyboard_activation_and_viewport_context(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is required to execute the repository browser controller")

        harness = r"""
const fs = require("fs");
const vm = require("vm");

class Element {
  constructor() {
    this.parentElement = null;
    this.attributes = new Map();
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); }
}
class HTMLElement extends Element {
  constructor() {
    super();
    this.dataset = {};
    this.inert = false;
    this.textContent = "";
    this.focusCount = 0;
  }
  focus() { this.focusCount += 1; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
}
class HTMLButtonElement extends HTMLElement {}
class HTMLAnchorElement extends HTMLElement {
  constructor() {
    super();
    this.href = "https://example.test/files/site/content/file.html";
  }
  closest(selector) {
    return selector === "a[data-repository-file]" ? this : null;
  }
}
class HTMLIFrameElement extends HTMLElement {}
class HTMLDetailsElement extends HTMLElement {
  constructor() {
    super();
    this.open = false;
  }
}

global.Element = Element;
global.HTMLElement = HTMLElement;
global.HTMLButtonElement = HTMLButtonElement;
global.HTMLAnchorElement = HTMLAnchorElement;
global.HTMLIFrameElement = HTMLIFrameElement;
global.HTMLDetailsElement = HTMLDetailsElement;

const tree = new HTMLElement();
const frame = new HTMLIFrameElement();
frame.setAttribute("srcdoc", "placeholder");
const content = new HTMLElement();
content.querySelector = (selector) =>
  selector === "iframe[name='repository-file-viewer']" ? frame : null;
const filesButton = new HTMLButtonElement();
const selectedFileLabel = new HTMLElement();
const fallbackTreeLink = new HTMLAnchorElement();
fallbackTreeLink.dataset.filePath = "fallback.md";
tree.querySelector = () => fallbackTreeLink;
tree.querySelectorAll = () => [];
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
const location = { hash: "" };
const history = {
  pushState(_state, _title, hash) { location.hash = hash; },
};
const windowHandlers = {};
global.window = {
  location,
  history,
  matchMedia: () => mobileViewport,
  requestAnimationFrame: (callback) => callback(),
  addEventListener(type, callback) { windowHandlers[type] = callback; },
};

function clickEvent(target, overrides = {}) {
  return {
    target,
    defaultPrevented: false,
    button: 0,
    detail: 0,
    metaKey: false,
    ctrlKey: false,
    shiftKey: false,
    altKey: false,
    preventDefault() { this.defaultPrevented = true; },
    ...overrides,
  };
}

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

buttonHandlers.click();
const noSelectionReturn = {
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
  fallbackFocusCount: fallbackTreeLink.focusCount,
};

const link = new HTMLAnchorElement();
link.dataset.filePath = "README.md";
link.textContent = "README.md";
browserHandlers.click(clickEvent(link, { ctrlKey: true }));
browserHandlers.click(clickEvent(link, { button: 1 }));
const modifiedClicks = {
  mode: browser.dataset.mobileView,
  current: link.getAttribute("aria-current"),
  filesButtonFocusCount: filesButton.focusCount,
};

browserHandlers.click(clickEvent(link));
const keyboardActivation = {
  mode: browser.dataset.mobileView,
  current: link.getAttribute("aria-current"),
  label: selectedFileLabel.textContent,
  treeInert: tree.inert,
  contentInert: content.inert,
  filesButtonFocusCount: filesButton.focusCount,
  hash: location.hash,
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
  noSelectionReturn,
  modifiedClicks,
  keyboardActivation,
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
            result["noSelectionReturn"],
            {
                "mode": "files",
                "treeInert": False,
                "contentInert": True,
                "fallbackFocusCount": 1,
            },
        )
        self.assertEqual(
            result["modifiedClicks"],
            {"mode": "files", "current": None, "filesButtonFocusCount": 0},
        )
        self.assertEqual(
            result["keyboardActivation"],
            {
                "mode": "content",
                "current": "true",
                "label": "README.md",
                "treeInert": True,
                "contentInert": False,
                "filesButtonFocusCount": 1,
                "hash": "#file=README.md",
            },
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
