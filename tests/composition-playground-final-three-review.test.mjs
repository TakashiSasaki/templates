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

const clipboardRequests = [];
const navigatorState = {
  clipboard: {
    writeText(text) {
      const request = deferred();
      request.text = text;
      clipboardRequests.push(request);
      return request.promise;
    },
  },
};
Object.defineProperty(globalThis, "navigator", { configurable: true, writable: true, value: navigatorState });

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolveValue, rejectValue) => {
    resolve = resolveValue;
    reject = rejectValue;
  });
  return { promise, resolve, reject };
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

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
        initial_plan: { action_counts: { create: 1 }, conflict_count: 0 },
      },
      {
        index: 1,
        resolved_components: ["artifact.skill", "capability.cli"],
        dependency_edges: [],
        contract_ids: [],
        material_ids: [],
        initial_plan: { action_counts: { create: 2 }, conflict_count: 0 },
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

async function mountHarness(name, hash = "#recipe=skill") {
  const harness = makeHarness(name);
  const rawProjection = projection();
  globalThis.fetch = async (url) => {
    if (url === `/${name}-projection.json`) return new Response(JSON.stringify(rawProjection), { status: 200 });
    if (url === `/${name}-provenance.json`) return new Response(JSON.stringify(provenance()), { status: 200 });
    throw new Error(`unexpected URL ${url}`);
  };
  locationState.hash = hash;
  const context = await playground.ensureMounted(harness.document);
  return { ...harness, context };
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

async function flush() {
  await Promise.resolve();
  await Promise.resolve();
}

test("selection errors have their own presentation category", () => {
  const invalidSelection = new playground.ProjectionError("INVALID_SELECTION", "unknown recipe");
  assert.equal(playground.statusForError(invalidSelection), playground.labels.invalidSelection);
  assert.doesNotMatch(playground.statusForError(invalidSelection), /projection|provenance/i);

  assert.equal(
    playground.statusForError(new playground.ProjectionError("PROJECTION_UNAVAILABLE", "offline")),
    playground.labels.unavailable,
  );
  assert.equal(
    playground.statusForError(new playground.ProjectionError("PROVENANCE_UNAVAILABLE", "offline")),
    playground.labels.provenanceUnavailable,
  );
  assert.match(
    playground.statusForError(new playground.ProjectionError("UNSUPPORTED_PROJECTION", "version")),
    /incompatible/i,
  );
  assert.match(
    playground.statusForError(new playground.ProjectionError("MALFORMED_PROJECTION", "bad shape")),
    /malformed/i,
  );
  assert.match(
    playground.statusForError(new playground.ProjectionError("MALFORMED_PROVENANCE", "bad identity")),
    /malformed/i,
  );
});

test("initial invalid owned hash fails closed with selection-specific status", async () => {
  const harness = await mountHarness("invalid-initial", "#recipe=unknown");
  try {
    assert.equal(harness.context, null);
    assert.equal(harness.app.hidden, true);
    assert.equal(harness.root.dataset.playgroundError, "INVALID_SELECTION");
    assert.equal(harness.status.textContent, playground.labels.invalidSelection);
    assert.doesNotMatch(harness.status.textContent, /projection|provenance/i);
  } finally {
    await unmount(harness);
  }
});

test("same-document invalid owned hash fails closed and valid or document hashes recover", async () => {
  const harness = await mountHarness("invalid-hashchange");
  assert.ok(harness.context);
  try {
    locationState.hash = "#recipe=unknown";
    dispatchHashChange();
    assert.equal(harness.app.hidden, true);
    assert.equal(harness.root.dataset.playgroundError, "INVALID_SELECTION");
    assert.equal(harness.status.textContent, playground.labels.invalidSelection);
    assert.doesNotMatch(harness.status.textContent, /projection|provenance/i);

    locationState.hash = "#recipe=skill&include=capability.cli";
    dispatchHashChange();
    assert.equal(harness.app.hidden, false);
    assert.equal("playgroundError" in harness.root.dataset, false);
    assert.equal(harness.status.textContent, playground.labels.loaded);
    assert.match(harness.config.textContent, /capability\.cli/);

    locationState.hash = "#recipe=unknown";
    dispatchHashChange();
    assert.equal(harness.app.hidden, true);
    locationState.hash = "#v1-scope";
    dispatchHashChange();
    assert.equal(harness.app.hidden, false);
    assert.equal(locationState.hash, "#v1-scope");
    assert.equal(harness.status.textContent, playground.labels.loaded);
  } finally {
    await unmount(harness);
  }
});

test("resolved outcomes reject either direction of a declared conflict", () => {
  const valid = projection();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const forward = clone(valid);
  forward.components[0].conflicts = ["capability.cli"];
  assert.throws(
    () => playground.validateProjection(forward),
    (error) => error.code === "MALFORMED_PROJECTION",
    "artifact declares a resolved capability conflict",
  );

  const reverse = clone(valid);
  reverse.components[1].conflicts = ["artifact.skill"];
  assert.throws(
    () => playground.validateProjection(reverse),
    (error) => error.code === "MALFORMED_PROJECTION",
    "capability declares a reverse-direction resolved artifact conflict",
  );
});

test("globally known conflict targets remain allowed when absent from the resolved outcome", () => {
  const valid = projection();
  valid.components.push({
    id: "capability.extra",
    role: "capability",
    version: 1,
    summary: "Unselected capability",
    requires: [],
    conflicts: [],
    contract_ids: [],
    material_declarations: [],
    source_path: "components/capability.extra/component.json",
  });
  valid.components[0].conflicts = ["capability.extra"];
  assert.doesNotThrow(() => playground.validateProjection(valid));
});

test("newer copy success owns feedback over older failure", async () => {
  clipboardRequests.length = 0;
  const harness = await mountHarness("copy-newer-success");
  assert.ok(harness.context);
  try {
    harness.copy.dispatch("click");
    harness.copy.dispatch("click");
    assert.equal(clipboardRequests.length, 2);

    clipboardRequests[1].resolve();
    await flush();
    assert.equal(harness.status.textContent, playground.labels.copied);

    clipboardRequests[0].reject(new Error("older failure"));
    await clipboardRequests[0].promise.catch(() => {});
    await flush();
    assert.equal(harness.status.textContent, playground.labels.copied);
  } finally {
    await unmount(harness);
  }
});

test("newer copy failure owns feedback over older success", async () => {
  clipboardRequests.length = 0;
  const harness = await mountHarness("copy-newer-failure");
  assert.ok(harness.context);
  try {
    harness.copy.dispatch("click");
    harness.copy.dispatch("click");
    assert.equal(clipboardRequests.length, 2);

    clipboardRequests[1].reject(new Error("newer failure"));
    await clipboardRequests[1].promise.catch(() => {});
    await flush();
    assert.equal(harness.status.textContent, playground.labels.copyFailed);

    clipboardRequests[0].resolve();
    await flush();
    assert.equal(harness.status.textContent, playground.labels.copyFailed);
  } finally {
    await unmount(harness);
  }
});

test("superseded copy completion is silent until the latest attempt completes", async () => {
  clipboardRequests.length = 0;
  const harness = await mountHarness("copy-superseded-first");
  assert.ok(harness.context);
  try {
    harness.copy.dispatch("click");
    harness.copy.dispatch("click");
    assert.equal(clipboardRequests.length, 2);
    const statusBefore = harness.status.textContent;

    clipboardRequests[0].resolve();
    await flush();
    assert.equal(harness.status.textContent, statusBefore);

    clipboardRequests[1].resolve();
    await flush();
    assert.equal(harness.status.textContent, playground.labels.copied);
  } finally {
    await unmount(harness);
  }
});

test("copy completion remains stale after selection change while clipboard content is not rewritten", async () => {
  clipboardRequests.length = 0;
  const harness = await mountHarness("copy-selection-stale");
  assert.ok(harness.context);
  try {
    harness.copy.dispatch("click");
    assert.equal(clipboardRequests.length, 1);
    const copiedRequest = clipboardRequests[0];
    assert.doesNotMatch(copiedRequest.text, /capability\.cli/);

    const checkbox = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    checkbox.checked = true;
    checkbox.dispatch("change");
    const statusAfterSelection = harness.status.textContent;
    assert.match(harness.config.textContent, /capability\.cli/);

    copiedRequest.resolve();
    await flush();
    assert.equal(harness.status.textContent, statusAfterSelection);
    assert.notEqual(harness.status.textContent, playground.labels.copied);
    assert.doesNotMatch(copiedRequest.text, /capability\.cli/);
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
