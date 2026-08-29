from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


class RepositoryBrowserDeepLinkTests(unittest.TestCase):
    def test_file_hash_restores_selection_and_tracks_history(self) -> None:
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
    this.focused = false;
  }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() { this.focused = true; }
}
class HTMLButtonElement extends HTMLElement {
  constructor() {
    super();
    this.listeners = {};
  }
  addEventListener(type, callback) { this.listeners[type] = callback; }
}
class HTMLAnchorElement extends HTMLElement {
  constructor(path, href) {
    super();
    this.dataset.filePath = path;
    this.href = href;
    this.textContent = path;
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

const details = new HTMLDetailsElement();
const first = new HTMLAnchorElement("AGENTS.md", "https://example.test/files/site/content/a.html");
const second = new HTMLAnchorElement("docs/Guide A.md", "https://example.test/files/site/content/b.html");
first.parentElement = details;
second.parentElement = details;

const tree = new HTMLElement();
details.parentElement = tree;
tree.querySelectorAll = (selector) => selector === "a[data-repository-file]" ? [first, second] : [];
tree.querySelector = () => first;

const frame = new HTMLIFrameElement();
frame.setAttribute("srcdoc", "placeholder");
const content = new HTMLElement();
content.querySelector = (selector) => selector === "iframe[name='repository-file-viewer']" ? frame : null;
const filesButton = new HTMLButtonElement();
const selectedFileLabel = new HTMLElement();
const browser = new HTMLElement();
browser.dataset.mobileView = "files";
const browserListeners = {};
browser.querySelector = (selector) => ({
  "[data-repository-tree]": tree,
  "[data-repository-content]": content,
  "[data-show-files]": filesButton,
  "[data-selected-file]": selectedFileLabel,
})[selector] || null;
browser.addEventListener = (type, callback) => { browserListeners[type] = callback; };
browser.contains = () => true;

global.document = {
  querySelector: () => browser,
  documentElement: { classList: { add() {} } },
};

const windowListeners = {};
const location = { hash: "#file=AGENTS.md" };
const pushed = [];
const history = {
  pushState(_state, _title, hash) {
    location.hash = hash;
    pushed.push(hash);
  },
};
const mobileViewport = {
  matches: true,
  addEventListener() {},
  addListener() {},
};
global.window = {
  location,
  history,
  matchMedia: () => mobileViewport,
  requestAnimationFrame: (callback) => callback(),
  addEventListener(type, callback) { windowListeners[type] = callback; },
};

vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {
  filename: process.argv[1],
});

const initial = {
  mode: browser.dataset.mobileView,
  label: selectedFileLabel.textContent,
  frameSrc: frame.getAttribute("src"),
  frameSrcdoc: frame.getAttribute("srcdoc"),
  firstCurrent: first.getAttribute("aria-current"),
  treeInert: tree.inert,
  contentInert: content.inert,
  ancestorOpen: details.open,
};

let prevented = false;
browserListeners.click({
  defaultPrevented: false,
  button: 0,
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  altKey: false,
  target: second,
  preventDefault() { prevented = true; },
});
const afterClick = {
  prevented,
  hash: location.hash,
  pushes: pushed.slice(),
  label: selectedFileLabel.textContent,
  frameSrc: frame.getAttribute("src"),
  firstCurrent: first.getAttribute("aria-current"),
  secondCurrent: second.getAttribute("aria-current"),
  mode: browser.dataset.mobileView,
  backFocused: filesButton.focused,
};

location.hash = "#file=AGENTS.md";
windowListeners.popstate();
const afterBack = {
  label: selectedFileLabel.textContent,
  frameSrc: frame.getAttribute("src"),
  firstCurrent: first.getAttribute("aria-current"),
  secondCurrent: second.getAttribute("aria-current"),
};

location.hash = "#file=missing.md";
windowListeners.hashchange();
const afterInvalid = {
  mode: browser.dataset.mobileView,
  label: selectedFileLabel.textContent,
  frameSrc: frame.getAttribute("src"),
  frameSrcdoc: frame.getAttribute("srcdoc"),
  firstCurrent: first.getAttribute("aria-current"),
  secondCurrent: second.getAttribute("aria-current"),
  treeInert: tree.inert,
  contentInert: content.inert,
};

process.stdout.write(JSON.stringify({ initial, afterClick, afterBack, afterInvalid }));
"""
        process = subprocess.run(
            [node, "-e", harness, str(CONTROLLER)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result = json.loads(process.stdout)

        initial = result["initial"]
        self.assertEqual(initial["mode"], "content")
        self.assertEqual(initial["label"], "AGENTS.md")
        self.assertEqual(
            initial["frameSrc"],
            "https://example.test/files/site/content/a.html",
        )
        self.assertIsNone(initial["frameSrcdoc"])
        self.assertEqual(initial["firstCurrent"], "true")
        self.assertTrue(initial["treeInert"])
        self.assertFalse(initial["contentInert"])
        self.assertTrue(initial["ancestorOpen"])

        after_click = result["afterClick"]
        self.assertTrue(after_click["prevented"])
        self.assertEqual(after_click["hash"], "#file=docs%2FGuide+A.md")
        self.assertEqual(after_click["pushes"], ["#file=docs%2FGuide+A.md"])
        self.assertEqual(after_click["label"], "docs/Guide A.md")
        self.assertEqual(
            after_click["frameSrc"],
            "https://example.test/files/site/content/b.html",
        )
        self.assertIsNone(after_click["firstCurrent"])
        self.assertEqual(after_click["secondCurrent"], "true")
        self.assertEqual(after_click["mode"], "content")
        self.assertTrue(after_click["backFocused"])

        after_back = result["afterBack"]
        self.assertEqual(after_back["label"], "AGENTS.md")
        self.assertEqual(
            after_back["frameSrc"],
            "https://example.test/files/site/content/a.html",
        )
        self.assertEqual(after_back["firstCurrent"], "true")
        self.assertIsNone(after_back["secondCurrent"])

        after_invalid = result["afterInvalid"]
        self.assertEqual(after_invalid["mode"], "files")
        self.assertEqual(after_invalid["label"], "Selected file")
        self.assertIsNone(after_invalid["frameSrc"])
        self.assertEqual(after_invalid["frameSrcdoc"], "placeholder")
        self.assertIsNone(after_invalid["firstCurrent"])
        self.assertIsNone(after_invalid["secondCurrent"])
        self.assertFalse(after_invalid["treeInert"])
        self.assertTrue(after_invalid["contentInert"])


if __name__ == "__main__":
    unittest.main()
