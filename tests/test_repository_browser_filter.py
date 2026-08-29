from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "assets/javascripts/repository-browser.js"


class RepositoryBrowserFilterTests(unittest.TestCase):
    def test_filter_keyboard_quick_open_and_mobile_context(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is required to execute the repository browser controller")

        harness = r"""
const fs = require("fs");
const vm = require("vm");

class Element {
  constructor(tagName = "DIV") {
    this.tagName = tagName;
    this.parentElement = null;
    this.children = [];
    this.attributes = new Map();
    this.style = {};
    this.hidden = false;
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
  contains(candidate) {
    let current = candidate;
    while (current) {
      if (current === this) return true;
      current = current.parentElement;
    }
    return false;
  }
  closest(selector) {
    let current = this;
    while (current) {
      if (selector === "a[data-repository-file]" && current instanceof HTMLAnchorElement) return current;
      if (
        selector === "input, textarea, select, [contenteditable='true']" &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(current.tagName)
      ) return current;
      current = current.parentElement;
    }
    return null;
  }
}
class HTMLElement extends Element {
  constructor(tagName = "DIV") {
    super(tagName);
    this.dataset = {};
    this.inert = false;
    this.textContent = "";
    this.listeners = {};
    this.scrollTop = 0;
    this.value = "";
  }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  focus() { document.activeElement = this; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
}
class HTMLButtonElement extends HTMLElement {
  constructor() { super("BUTTON"); this.disabled = false; this.type = "button"; }
}
class HTMLAnchorElement extends HTMLElement {
  constructor(path, href) {
    super("A");
    this.dataset.filePath = path;
    this.href = href;
    this.textContent = path;
  }
}
class HTMLIFrameElement extends HTMLElement { constructor() { super("IFRAME"); } }
class HTMLDetailsElement extends HTMLElement {
  constructor() { super("DETAILS"); this.open = false; }
}

global.Element = Element;
global.HTMLElement = HTMLElement;
global.HTMLButtonElement = HTMLButtonElement;
global.HTMLAnchorElement = HTMLAnchorElement;
global.HTMLIFrameElement = HTMLIFrameElement;
global.HTMLDetailsElement = HTMLDetailsElement;

function li() { return new HTMLElement("LI"); }
function rowFor(link) {
  const row = new HTMLElement("SPAN");
  row.appendChild(link);
  return row;
}

const guideA = new HTMLAnchorElement("docs/Guide A.md", "https://example.test/files/site/content/a.html");
const guideB = new HTMLAnchorElement("docs/Guide B.md", "https://example.test/files/site/content/b.html");
const agents = new HTMLAnchorElement("AGENTS.md", "https://example.test/files/site/content/agents.html");

const guideALi = li();
guideALi.appendChild(rowFor(guideA));
const guideBLi = li();
guideBLi.appendChild(rowFor(guideB));
const docsChildren = new HTMLElement("UL");
docsChildren.appendChild(guideALi);
docsChildren.appendChild(guideBLi);
const docsDetails = new HTMLDetailsElement();
docsDetails.open = false;
docsDetails.appendChild(new HTMLElement("SUMMARY"));
docsDetails.appendChild(docsChildren);
const docsLi = li();
docsLi.appendChild(docsDetails);
const agentsLi = li();
agentsLi.appendChild(rowFor(agents));
const rootList = new HTMLElement("UL");
rootList.appendChild(docsLi);
rootList.appendChild(agentsLi);

const browserHeader = new HTMLElement("DIV");
const treeScroller = new HTMLElement("DIV");
treeScroller.appendChild(rootList);
const tree = new HTMLElement("ASIDE");
tree.appendChild(browserHeader);
tree.appendChild(treeScroller);
tree.querySelector = (selector) => {
  if (selector === ".browser-header") return browserHeader;
  if (selector === ".tree") return treeScroller;
  return null;
};
tree.querySelectorAll = (selector) => {
  if (selector === "a[data-repository-file]") return [guideA, guideB, agents];
  if (selector === ".tree li") return [docsLi, guideALi, guideBLi, agentsLi];
  if (selector === ".tree details") return [docsDetails];
  return [];
};

const frame = new HTMLIFrameElement();
frame.setAttribute("srcdoc", "placeholder");
const content = new HTMLElement("MAIN");
content.querySelector = (selector) => {
  if (selector === "iframe[name='repository-file-viewer']") return frame;
  if (selector === ".viewer-mobile-toolbar") return null;
  return null;
};

const filesButton = new HTMLButtonElement();
const selectedFileLabel = new HTMLElement("SPAN");
const browser = new HTMLElement("DIV");
browser.dataset.mobileView = "files";
browser.querySelector = (selector) => ({
  "[data-repository-tree]": tree,
  "[data-repository-content]": content,
  "[data-show-files]": filesButton,
  "[data-selected-file]": selectedFileLabel,
})[selector] || null;
browser.contains = (candidate) => tree.contains(candidate) || content.contains(candidate);

const documentListeners = {};
global.document = {
  body: new HTMLElement("BODY"),
  activeElement: null,
  querySelector: () => browser,
  documentElement: { classList: { add() {} } },
  addEventListener(type, callback) { documentListeners[type] = callback; },
  createElement(tag) {
    const upper = tag.toUpperCase();
    if (upper === "BUTTON") return new HTMLButtonElement();
    return new HTMLElement(upper);
  },
};

const windowListeners = {};
const location = { href: "https://example.test/files/site/", hash: "" };
const pushed = [];
const history = {
  pushState(_state, _title, hash) {
    pushed.push(hash);
    location.hash = hash;
    location.href = `https://example.test/files/site/${hash}`;
  },
};
const mobileViewport = {
  matches: true,
  addEventListener() {},
};
global.window = {
  isSecureContext: true,
  location,
  history,
  matchMedia: () => mobileViewport,
  requestAnimationFrame: (callback) => callback(),
  addEventListener(type, callback) { windowListeners[type] = callback; },
};

vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"), { filename: process.argv[1] });

const filterControls = browserHeader.children.find(
  (child) => child.getAttribute("data-repository-filter") === ""
);
if (!(filterControls instanceof HTMLElement)) throw new Error("filter controls were not created");
const filterInput = filterControls.children.find((child) => child.tagName === "INPUT");
const filterStatus = filterControls.children.find(
  (child) => child.getAttribute("data-repository-filter-status") === ""
);
if (!(filterInput instanceof HTMLElement) || !(filterStatus instanceof HTMLElement)) {
  throw new Error("filter input/status missing");
}

function keyEvent(key, target = filterInput) {
  return {
    key,
    target,
    defaultPrevented: false,
    metaKey: false,
    ctrlKey: false,
    altKey: false,
    prevented: false,
    preventDefault() { this.prevented = true; this.defaultPrevented = true; },
  };
}

const initial = {
  placeholder: filterInput.placeholder,
  label: filterInput.getAttribute("aria-label"),
  status: filterStatus.textContent,
  detailsOpen: docsDetails.open,
};

filterInput.value = "gUiDe a";
filterInput.listeners.input({});
const matched = {
  docsHidden: docsLi.hidden,
  aHidden: guideALi.hidden,
  bHidden: guideBLi.hidden,
  agentsHidden: agentsLi.hidden,
  detailsOpen: docsDetails.open,
  status: filterStatus.textContent,
};

const escapeEvent = keyEvent("Escape");
filterInput.listeners.keydown(escapeEvent);
const cleared = {
  prevented: escapeEvent.prevented,
  value: filterInput.value,
  docsHidden: docsLi.hidden,
  aHidden: guideALi.hidden,
  bHidden: guideBLi.hidden,
  agentsHidden: agentsLi.hidden,
  detailsOpen: docsDetails.open,
  status: filterStatus.textContent,
};

filterInput.value = "does-not-exist";
filterInput.listeners.input({});
const zero = {
  docsHidden: docsLi.hidden,
  agentsHidden: agentsLi.hidden,
  status: filterStatus.textContent,
};

filterInput.value = "guide";
filterInput.listeners.input({});
treeScroller.scrollTop = 137;
filterInput.focus();
const enterEvent = keyEvent("Enter");
filterInput.listeners.keydown(enterEvent);
const opened = {
  prevented: enterEvent.prevented,
  mode: browser.dataset.mobileView,
  filterValue: filterInput.value,
  selected: selectedFileLabel.textContent,
  frameSrc: frame.getAttribute("src"),
  frameSrcdoc: frame.getAttribute("srcdoc"),
  hash: location.hash,
  pushed: pushed.slice(),
  focusedFilesButton: document.activeElement === filesButton,
};

filesButton.listeners.click();
const returned = {
  mode: browser.dataset.mobileView,
  filterValue: filterInput.value,
  scrollTop: treeScroller.scrollTop,
  focusedFilter: document.activeElement === filterInput,
  guideAHidden: guideALi.hidden,
  guideBHidden: guideBLi.hidden,
  agentsHidden: agentsLi.hidden,
};

browser.dataset.mobileView = "content";
document.activeElement = filesButton;
const slashEvent = keyEvent("/", filesButton);
documentListeners.keydown(slashEvent);
const slash = {
  prevented: slashEvent.prevented,
  mode: browser.dataset.mobileView,
  focusedFilter: document.activeElement === filterInput,
  filterValue: filterInput.value,
};

const editableSlash = keyEvent("/", filterInput);
documentListeners.keydown(editableSlash);
const editable = { prevented: editableSlash.prevented };

process.stdout.write(JSON.stringify({ initial, matched, cleared, zero, opened, returned, slash, editable }));
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
                "placeholder": "Filter files…",
                "label": "Filter files",
                "status": "3 files",
                "detailsOpen": False,
            },
        )
        self.assertEqual(
            result["matched"],
            {
                "docsHidden": False,
                "aHidden": False,
                "bHidden": True,
                "agentsHidden": True,
                "detailsOpen": True,
                "status": "1 of 3 files",
            },
        )
        self.assertEqual(
            result["cleared"],
            {
                "prevented": True,
                "value": "",
                "docsHidden": False,
                "aHidden": False,
                "bHidden": False,
                "agentsHidden": False,
                "detailsOpen": False,
                "status": "3 files",
            },
        )
        self.assertEqual(
            result["zero"],
            {
                "docsHidden": True,
                "agentsHidden": True,
                "status": "No matching files",
            },
        )
        self.assertEqual(
            result["opened"],
            {
                "prevented": True,
                "mode": "content",
                "filterValue": "guide",
                "selected": "docs/Guide A.md",
                "frameSrc": "https://example.test/files/site/content/a.html",
                "frameSrcdoc": None,
                "hash": "#file=docs%2FGuide+A.md",
                "pushed": ["#file=docs%2FGuide+A.md"],
                "focusedFilesButton": True,
            },
        )
        self.assertEqual(
            result["returned"],
            {
                "mode": "files",
                "filterValue": "guide",
                "scrollTop": 137,
                "focusedFilter": True,
                "guideAHidden": False,
                "guideBHidden": False,
                "agentsHidden": True,
            },
        )
        self.assertEqual(
            result["slash"],
            {
                "prevented": True,
                "mode": "files",
                "focusedFilter": True,
                "filterValue": "guide",
            },
        )
        self.assertEqual(result["editable"], {"prevented": False})


if __name__ == "__main__":
    unittest.main()
