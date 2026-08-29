from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


class RepositoryBrowserModernListenerTests(unittest.TestCase):
    def test_modern_media_query_listener_is_registered_and_executed(self) -> None:
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
  }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() {}
}
class HTMLButtonElement extends HTMLElement {
  addEventListener() {}
}
class HTMLAnchorElement extends HTMLElement {}
class HTMLIFrameElement extends HTMLElement {}
class HTMLDetailsElement extends HTMLElement {}

global.Element = Element;
global.HTMLElement = HTMLElement;
global.HTMLButtonElement = HTMLButtonElement;
global.HTMLAnchorElement = HTMLAnchorElement;
global.HTMLIFrameElement = HTMLIFrameElement;
global.HTMLDetailsElement = HTMLDetailsElement;

const tree = new HTMLElement();
const content = new HTMLElement();
const filesButton = new HTMLButtonElement();
const selectedFileLabel = new HTMLElement();
const browser = new HTMLElement();
browser.dataset.mobileView = "files";
browser.querySelector = (selector) => ({
  "[data-repository-tree]": tree,
  "[data-repository-content]": content,
  "[data-show-files]": filesButton,
  "[data-selected-file]": selectedFileLabel,
})[selector] || null;
browser.addEventListener = () => {};
browser.contains = () => true;

global.document = {
  querySelector: () => browser,
  documentElement: { classList: { add() {} } },
};

let viewportListener = null;
let legacyCalls = 0;
const mobileViewport = {
  matches: false,
  addEventListener(type, callback) {
    if (type === "change") viewportListener = callback;
  },
  addListener() { legacyCalls += 1; },
};
global.window = {
  matchMedia: () => mobileViewport,
  requestAnimationFrame: (callback) => callback(),
  addEventListener() {},
};

vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {
  filename: process.argv[1],
});
if (typeof viewportListener !== "function") {
  throw new Error("modern MediaQueryList change listener was not registered");
}

mobileViewport.matches = true;
viewportListener({ matches: true });
process.stdout.write(JSON.stringify({
  legacyCalls,
  mode: browser.dataset.mobileView,
  treeInert: tree.inert,
  contentInert: content.inert,
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
        self.assertEqual(result["legacyCalls"], 0)
        self.assertEqual(result["mode"], "files")
        self.assertFalse(result["treeInert"])
        self.assertTrue(result["contentInert"])


if __name__ == "__main__":
    unittest.main()
