from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


class RepositoryBrowserSharingTests(unittest.TestCase):
    def test_selected_file_copy_controls_use_canonical_targets(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is required to execute the repository browser controller")

        harness = r"""
const fs = require("fs");
const vm = require("vm");

class Element {
  constructor() {
    this.parentElement = null;
    this.children = [];
    this.attributes = new Map();
    this.style = {};
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); }
  appendChild(child) {
    if (child.parentElement) {
      child.parentElement.children = child.parentElement.children.filter((item) => item !== child);
    }
    child.parentElement = this;
    this.children.push(child);
    return child;
  }
  remove() {
    if (this.parentElement) {
      this.parentElement.children = this.parentElement.children.filter((item) => item !== this);
      this.parentElement = null;
    }
  }
}
class HTMLElement extends Element {
  constructor() {
    super();
    this.dataset = {};
    this.inert = false;
    this.textContent = "";
    this.listeners = {};
  }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  focus() {}
  select() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
}
class HTMLButtonElement extends HTMLElement {
  constructor() {
    super();
    this.disabled = false;
    this.type = "button";
  }
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
class HTMLTextAreaElement extends HTMLElement {
  constructor() {
    super();
    this.value = "";
  }
}

global.Element = Element;
global.HTMLElement = HTMLElement;
global.HTMLButtonElement = HTMLButtonElement;
global.HTMLAnchorElement = HTMLAnchorElement;
global.HTMLIFrameElement = HTMLIFrameElement;
global.HTMLDetailsElement = HTMLDetailsElement;

const source = new HTMLAnchorElement(
  "source",
  "https://github.com/TakashiSasaki/templates/blob/0123456789abcdef0123456789abcdef01234567/AGENTS.md"
);
const file = new HTMLAnchorElement(
  "AGENTS.md",
  "https://example.test/files/site/content/file.html"
);
const row = new HTMLElement();
row.querySelector = (selector) => selector === "a.tree-source" ? source : null;
row.appendChild(file);
row.appendChild(source);

const browserHeader = new HTMLElement();
const tree = new HTMLElement();
tree.appendChild(browserHeader);
tree.appendChild(row);
tree.querySelectorAll = (selector) => selector === "a[data-repository-file]" ? [file] : [];
tree.querySelector = (selector) => selector === ".browser-header" ? browserHeader : file;

const frame = new HTMLIFrameElement();
frame.setAttribute("srcdoc", "placeholder");
const mobileToolbar = new HTMLElement();
const content = new HTMLElement();
content.querySelector = (selector) => {
  if (selector === "iframe[name='repository-file-viewer']") return frame;
  if (selector === ".viewer-mobile-toolbar") return mobileToolbar;
  return null;
};
content.appendChild(mobileToolbar);
content.appendChild(frame);

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
browser.contains = () => true;

const body = new HTMLElement();
global.document = {
  body,
  querySelector: () => browser,
  documentElement: { classList: { add() {} } },
  createElement(tag) {
    if (tag === "button") return new HTMLButtonElement();
    if (tag === "textarea") return new HTMLTextAreaElement();
    return new HTMLElement();
  },
  execCommand() { throw new Error("secure clipboard path should be used"); },
};

const copied = [];
Object.defineProperty(global, "navigator", {
  configurable: true,
  value: { clipboard: { writeText: async (value) => { copied.push(value); } } },
});

const windowListeners = {};
const location = {
  href: "https://example.test/files/site/#file=AGENTS.md",
  hash: "#file=AGENTS.md",
};
const history = {
  pushState(_state, _title, hash) {
    location.hash = hash;
    location.href = `https://example.test/files/site/${hash}`;
  },
};
let viewportListener = null;
const mobileViewport = {
  matches: false,
  addEventListener(type, callback) {
    if (type === "change") viewportListener = callback;
  },
};
global.window = {
  isSecureContext: true,
  location,
  history,
  matchMedia: () => mobileViewport,
  requestAnimationFrame: (callback) => callback(),
  addEventListener(type, callback) { windowListeners[type] = callback; },
};

vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), {
  filename: process.argv[1],
});

const share = browserHeader.children.find(
  (child) => child.getAttribute("data-repository-share") === ""
);
if (!(share instanceof HTMLElement)) throw new Error("share controls were not created");
const buttons = Object.fromEntries(
  share.children
    .filter((child) => child instanceof HTMLButtonElement)
    .map((button) => [button.dataset.copyRepository, button])
);
const status = share.children.find(
  (child) => child.getAttribute("data-repository-share-status") === ""
);

(async () => {
  const initial = {
    parentIsHeader: share.parentElement === browserHeader,
    marginTop: share.style.marginTop,
    selected: selectedFileLabel.textContent,
    labels: Object.fromEntries(Object.entries(buttons).map(([kind, button]) => [kind, button.textContent])),
    disabled: Object.fromEntries(Object.entries(buttons).map(([kind, button]) => [kind, button.disabled])),
  };

  await buttons.path.listeners.click();
  const pathStatus = status.textContent;
  await buttons.viewer.listeners.click();
  const viewerStatus = status.textContent;
  await buttons.source.listeners.click();
  const sourceStatus = status.textContent;

  mobileViewport.matches = true;
  viewportListener({ matches: true });
  const mobile = {
    parentIsToolbar: share.parentElement === mobileToolbar,
    marginTop: share.style.marginTop,
  };

  location.hash = "#file=missing.md";
  location.href = "https://example.test/files/site/#file=missing.md";
  windowListeners.hashchange();
  const invalid = {
    mode: browser.dataset.mobileView,
    label: selectedFileLabel.textContent,
    disabled: Object.fromEntries(Object.entries(buttons).map(([kind, button]) => [kind, button.disabled])),
    status: status.textContent,
    frameSrc: frame.getAttribute("src"),
    frameSrcdoc: frame.getAttribute("srcdoc"),
  };

  process.stdout.write(JSON.stringify({
    initial,
    copied,
    pathStatus,
    viewerStatus,
    sourceStatus,
    mobile,
    invalid,
  }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
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
            result["initial"],
            {
                "parentIsHeader": True,
                "marginTop": ".6rem",
                "selected": "AGENTS.md",
                "labels": {
                    "path": "Copy path",
                    "viewer": "Copy viewer link",
                    "source": "Copy immutable source link",
                },
                "disabled": {"path": False, "viewer": False, "source": False},
            },
        )
        self.assertEqual(
            result["copied"],
            [
                "AGENTS.md",
                "https://example.test/files/site/#file=AGENTS.md",
                "https://github.com/TakashiSasaki/templates/blob/"
                "0123456789abcdef0123456789abcdef01234567/AGENTS.md",
            ],
        )
        self.assertEqual(result["pathStatus"], "Copied path")
        self.assertEqual(result["viewerStatus"], "Copied viewer link")
        self.assertEqual(result["sourceStatus"], "Copied immutable source link")
        self.assertEqual(
            result["mobile"],
            {"parentIsToolbar": True, "marginTop": "0"},
        )
        self.assertEqual(
            result["invalid"],
            {
                "mode": "files",
                "label": "Selected file",
                "disabled": {"path": True, "viewer": True, "source": True},
                "status": "",
                "frameSrc": None,
                "frameSrcdoc": "placeholder",
            },
        )


if __name__ == "__main__":
    unittest.main()
