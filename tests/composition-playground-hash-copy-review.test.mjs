import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

class FakeNode {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.listeners = new Map();
    this.dataset = {};
    this.hidden = false;
    this.textContent = "";
    this.value = "";
    this.type = "";
    this.checked = false;
    this.selected = false;
    this.className = "";
    this.isConnected = true;
  }

  get firstChild() {
    return this.children[0] || null;
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    if (this.tagName === "SELECT" && child.tagName === "OPTION" && child.selected) {
      this.value = child.value;
    }
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    child.parentNode = null;
    return child;
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }

  dispatch(type) {
    for (const listener of this.listeners.get(type) || []) listener({ target: this });
  }

  querySelectorAll(selector) {
    const matches = [];
    const walk = (node) => {
      for (const child of node.children) {
        const checkbox = child.tagName === "INPUT" && child.type === "checkbox";
        if (
          (selector === "input[type=checkbox]" && checkbox) ||
          (selector === "input[type=checkbox]:checked" && checkbox && child.checked)
        ) {
          matches.push(child);
        }
        walk(child);
      }
    };
    walk(this);
    return matches;
  }
}

const originalGlobals = {
  fetch: globalThis.fetch,
  location: globalThis.location,
  history: globalThis.history,
  navigator: globalThis.navigator,
  addEventListener: globalThis.addEventListener,
};

const windowListeners = new Map();
globalThis.addEventListener = (type, listener) => {
  if (!windowListeners.has(type)) windowListeners.set(type, []);
  windowListeners.get(type).push(listener);
};

const locationState = { pathname: "/playground/", search: "", hash: "#recipe=skill" };
Object.defineProperty(globalThis, "location", { configurable: true, writable: true, value: locationState });
Object.defineProperty(globalThis, "history", {
  configurable: true,
  writable: true,
  value: {
    replaceState(_state, _title, url) { locationState.hash = new URL(url, "https://example.test").hash; },
    pushState(_state, _title, url) { locationState.hash = new URL(url, "https://example.test").hash; },
  },
});

let copiedText = "";
const navigatorState = {
  clipboard: {
    async writeText(text) {
      copiedText = text;
    },
  },
};
Object.defineProperty(globalThis, "navigator", { configurable: true, writable: true, value: navigatorState });

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function projection() {
  return {
    schema_version: 1,
    projection_id: "composition-playground-v1",
    source: {
      repository: "TakashiSasaki/templates",
      authority: "composition",
      revision: "a".repeat(40),
    },
    scope: {
      mode: "initial",
      target: "empty",
      configuration_schema_version: 1,
      components_exclude: [],
      parameters: {},
    },
    provenance_reason_bits: {
      recipe_artifact: 1,
      recipe_required: 2,
      recipe_default: 4,
      explicit_include: 8,
      dependency: 16,
    },
    recipes: [{
      id: "skill",
      artifact: "artifact.skill",
      required_components: [],
      default_components: [],
      optional_components: ["capability.cli"],
      case_count: 2,
      source_path: "recipes/skill.json",
      cases: [
        { valid: true, error: null, outcome_id: 0, selection_reason_masks: [1] },
        { valid: true, error: null, outcome_id: 1, selection_reason_masks: [1, 8] },
      ],
    }],
    components: [
      {
        id: "artifact.skill",
        role: "artifact",
        version: 1,
        summary: "Skill artifact",
        requires: [],
        conflicts: [],
        contract_ids: [],
        material_declarations: [],
        source_path: "components/artifact.skill/component.json",
      },
      {
        id: "capability.cli",
        role: "capability",
        version: 1,
        summary: "CLI capability",
        requires: [],
        conflicts: [],
        contract_ids: [],
        material_declarations: [],
        source_path: "components/capability.cli/component.json",
      },
    ],
    contracts: [],
    materials: [],
    outcomes: [
      {
        index: 0,
        resolved_components: ["artifact.skill"],
        dependency_edges: [],
        contract_ids: [],
        material_ids: [],
        initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
      },
      {
        index: 1,
        resolved_components: ["artifact.skill", "capability.cli"],
        dependency_edges: [],
        contract_ids: [],
        material_ids: [],
        initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
      },
    ],
  };
}

function provenance() {
  return {
    schema_version: 2,
    repository: "TakashiSasaki/templates",
    site_commit: "c".repeat(40),
    publication_commits: {
      composition: "b".repeat(40),
      policy: "d".repeat(40),
    },
  };
}

function makeHarness(name) {
  const selectors = new Map();
  const status = new FakeNode("p");
  const app = new FakeNode("div");
  app.hidden = true;
  const recipe = new FakeNode("select");
  const optionals = new FakeNode("div");
  const validity = new FakeNode("p");
  const semanticRevision = new FakeNode("code");
  const providerRevision = new FakeNode("code");
  const projectionId = new FakeNode("code");
  const resolved = new FakeNode("ul");
  const config = new FakeNode("pre");
  const copy = new FakeNode("button");
  selectors.set("[data-playground-status]", status);
  selectors.set("[data-playground-app]", app);
  selectors.set("[data-playground-recipe]", recipe);
  selectors.set("[data-playground-optionals]", optionals);
  selectors.set("[data-playground-validity]", validity);
  selectors.set("[data-playground-semantic-revision]", semanticRevision);
  selectors.set("[data-playground-provider-revision]", providerRevision);
  selectors.set("[data-playground-projection-id]", projectionId);
  selectors.set("[data-playground-resolved]", resolved);
  selectors.set("[data-playground-config]", config);
  selectors.set("[data-playground-copy]", copy);

  const root = new FakeNode("div");
  root.dataset.projectionUrl = `/${name}-projection.json`;
  root.dataset.provenanceUrl = `/${name}-provenance.json`;
  root.querySelector = (selector) => selectors.get(selector) || null;

  const document = {
    currentRoot: root,
    createElement(tagName) { return new FakeNode(tagName); },
    createTextNode(text) {
      const node = new FakeNode("#text");
      node.textContent = text;
      return node;
    },
    getElementById(id) {
      return id === "composition-playground" ? this.currentRoot : null;
    },
  };
  return { root, document, status, app, recipe, optionals, config, copy };
}

async function mountHarness(name) {
  const harness = makeHarness(name);
  const rawProjection = projection();
  globalThis.fetch = async (url) => {
    if (url === `/${name}-projection.json`) return new Response(JSON.stringify(rawProjection), { status: 200 });
    if (url === `/${name}-provenance.json`) return new Response(JSON.stringify(provenance()), { status: 200 });
    throw new Error(`unexpected URL ${url}`);
  };
  locationState.hash = "#recipe=skill";
  const context = await playground.ensureMounted(harness.document);
  assert.ok(context);
  assert.equal(harness.status.textContent, playground.labels.loaded);
  return harness;
}

async function unmount(harness) {
  harness.document.currentRoot = null;
  await playground.ensureMounted(harness.document);
}

function dispatchHashChange() {
  const listeners = windowListeners.get("hashchange") || [];
  assert.equal(listeners.length, 1, "core should bind exactly one hashchange listener");
  for (const listener of listeners) listener();
}

test("same-document invalid owned hashes fail closed and a later valid hash recovers", async () => {
  const harness = await mountHarness("hash-review");
  const observed = [];
  const unsubscribe = playground.subscribe((event) => observed.push(event.type));
  try {
    locationState.hash = "#recipe=unknown";
    dispatchHashChange();
    assert.equal(harness.app.hidden, true);
    assert.equal(harness.root.dataset.playgroundError, "INVALID_SELECTION");
    assert.match(harness.status.textContent, /malformed and was rejected/);
    assert.equal(observed.at(-1), "error");

    locationState.hash = "#recipe=skill&include=capability.cli";
    dispatchHashChange();
    assert.equal(harness.app.hidden, false);
    assert.equal("playgroundError" in harness.root.dataset, false);
    assert.equal(harness.status.textContent, playground.labels.loaded);
    assert.match(harness.config.textContent, /capability\.cli/);
    assert.equal(observed.at(-1), "selection");

    locationState.hash = "#recipe=unknown";
    dispatchHashChange();
    assert.equal(harness.app.hidden, true);
    locationState.hash = "#v1-scope";
    dispatchHashChange();
    assert.equal(harness.app.hidden, false);
    assert.equal(locationState.hash, "#v1-scope");
    assert.equal(harness.status.textContent, playground.labels.loaded);
  } finally {
    unsubscribe();
    await unmount(harness);
  }
});

test("successful copy feedback is cleared when the validated selection changes", async () => {
  copiedText = "";
  const harness = await mountHarness("copy-review");
  try {
    harness.copy.dispatch("click");
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(harness.status.textContent, playground.labels.copied);
    assert.match(copiedText, /"recipe": "skill"/);
    assert.doesNotMatch(copiedText, /capability\.cli/);

    const checkbox = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    checkbox.checked = true;
    checkbox.dispatch("change");
    assert.equal(harness.status.textContent, playground.labels.loaded);
    assert.notEqual(harness.status.textContent, playground.labels.copied);
    assert.match(harness.config.textContent, /capability\.cli/);
  } finally {
    await unmount(harness);
  }
});

test.after(() => {
  Object.defineProperty(globalThis, "fetch", { configurable: true, writable: true, value: originalGlobals.fetch });
  if (originalGlobals.location === undefined) delete globalThis.location;
  else Object.defineProperty(globalThis, "location", { configurable: true, writable: true, value: originalGlobals.location });
  if (originalGlobals.history === undefined) delete globalThis.history;
  else Object.defineProperty(globalThis, "history", { configurable: true, writable: true, value: originalGlobals.history });
  if (originalGlobals.navigator === undefined) delete globalThis.navigator;
  else Object.defineProperty(globalThis, "navigator", { configurable: true, writable: true, value: originalGlobals.navigator });
  if (originalGlobals.addEventListener === undefined) delete globalThis.addEventListener;
  else globalThis.addEventListener = originalGlobals.addEventListener;
});
