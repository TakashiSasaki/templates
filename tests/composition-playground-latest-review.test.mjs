import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

class FakeNode {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.children = [];
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
    this.children.push(child);
    if (this.tagName === "SELECT" && child.tagName === "OPTION" && child.selected) this.value = child.value;
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    return child;
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }

  querySelectorAll(selector) {
    const matches = [];
    const walk = (node) => {
      for (const child of node.children) {
        const checkbox = child.tagName === "INPUT" && child.type === "checkbox";
        if (selector === "input[type=checkbox]:checked" && checkbox && child.checked) matches.push(child);
        walk(child);
      }
    };
    walk(this);
    return matches;
  }
}

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
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  writable: true,
  value: { clipboard: { async writeText() {} } },
});

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function projection() {
  return {
    schema_version: 1,
    projection_id: "composition-playground-v1",
    source: { repository: "TakashiSasaki/templates", authority: "composition", revision: "a".repeat(40) },
    scope: { mode: "initial", target: "empty", configuration_schema_version: 1, components_exclude: [], parameters: {} },
    provenance_reason_bits: { recipe_artifact: 1, recipe_required: 2, recipe_default: 4, explicit_include: 8, dependency: 16 },
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
      { id: "artifact.skill", role: "artifact", version: 1, summary: "Skill", requires: [], conflicts: [], contract_ids: [], material_declarations: [], source_path: "components/artifact.skill/component.json" },
      { id: "capability.cli", role: "capability", version: 1, summary: "CLI", requires: [], conflicts: [], contract_ids: [], material_declarations: [], source_path: "components/capability.cli/component.json" },
    ],
    contracts: [],
    materials: [],
    outcomes: [
      { index: 0, resolved_components: ["artifact.skill"], dependency_edges: [], contract_ids: [], material_ids: [], initial_plan: { action_counts: { create: 0 }, conflict_count: 0 } },
      { index: 1, resolved_components: ["artifact.skill", "capability.cli"], dependency_edges: [], contract_ids: [], material_ids: [], initial_plan: { action_counts: { create: 0 }, conflict_count: 0 } },
    ],
  };
}

function provenance() {
  return {
    schema_version: 2,
    repository: "TakashiSasaki/templates",
    site_commit: "c".repeat(40),
    publication_commits: { composition: "b".repeat(40), policy: "d".repeat(40) },
  };
}

function makeHarness(name) {
  const selectors = new Map();
  for (const selector of [
    "[data-playground-status]", "[data-playground-app]", "[data-playground-recipe]",
    "[data-playground-optionals]", "[data-playground-validity]", "[data-playground-semantic-revision]",
    "[data-playground-provider-revision]", "[data-playground-projection-id]", "[data-playground-resolved]",
    "[data-playground-config]", "[data-playground-copy]"
  ]) selectors.set(selector, new FakeNode(selector.includes("recipe") ? "select" : "div"));
  selectors.get("[data-playground-app]").hidden = true;
  const root = new FakeNode("div");
  root.dataset.projectionUrl = `/${name}-projection.json`;
  root.dataset.provenanceUrl = `/${name}-provenance.json`;
  root.querySelector = (selector) => selectors.get(selector) || null;
  const document = {
    currentRoot: root,
    createElement(tagName) { return new FakeNode(tagName); },
    createTextNode(text) { const node = new FakeNode("#text"); node.textContent = text; return node; },
    getElementById(id) { return id === "composition-playground" ? this.currentRoot : null; },
  };
  return { root, document, app: selectors.get("[data-playground-app]") };
}

async function mountHarness(name, hash) {
  const harness = makeHarness(name);
  globalThis.fetch = async (url) => {
    if (url === `/${name}-projection.json`) return new Response(JSON.stringify(projection()), { status: 200 });
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
  assert.equal(listeners.length, 1);
  for (const listener of listeners) listener();
}

test("material destinations reject ancestor/descendant collisions", () => {
  const value = projection();
  value.materials = [
    { index: 0, component: "artifact.skill", destination: "README.md", ownership: "seed", sha256: "0".repeat(64) },
    { index: 1, component: "artifact.skill", destination: "README.md/child.txt", ownership: "seed", sha256: "1".repeat(64) },
  ];
  for (const outcome of value.outcomes) {
    outcome.material_ids = [0, 1];
    outcome.initial_plan.action_counts = { create: 2 };
  }
  assert.throws(() => playground.validateProjection(value), (error) => error.code === "MALFORMED_PROJECTION");
});

test("empty-target initial plan count must equal projected material count", () => {
  const valid = projection();
  valid.materials = [
    { index: 0, component: "artifact.skill", destination: "README.md", ownership: "seed", sha256: "0".repeat(64) },
  ];
  for (const outcome of valid.outcomes) {
    outcome.material_ids = [0];
    outcome.initial_plan.action_counts = { create: 1 };
  }
  assert.doesNotThrow(() => playground.validateProjection(valid));

  for (const counts of [{}, { create: 0 }, { create: 2 }, { create: 1, replace: 0 }]) {
    const invalid = clone(valid);
    invalid.outcomes[0].initial_plan.action_counts = counts;
    assert.throws(() => playground.validateProjection(invalid), (error) => error.code === "MALFORMED_PROJECTION");
  }
});

test("initial invalid owned hash installs recovery handler", async () => {
  const harness = await mountHarness("initial-invalid-recovery", "#recipe=unknown");
  try {
    assert.equal(harness.context, null);
    assert.equal(harness.root.dataset.playgroundError, "INVALID_SELECTION");
    locationState.hash = "#recipe=skill";
    dispatchHashChange();
    const recovered = await playground.ensureMounted(harness.document);
    assert.ok(recovered);
    assert.equal(recovered.state.recipeId, "skill");
    assert.equal(harness.app.hidden, false);
  } finally {
    await unmount(harness);
  }
});

test("repeated mounts return the active context and null after fail-close", async () => {
  const harness = await mountHarness("repeat-current-context", "#recipe=skill");
  try {
    assert.ok(harness.context);
    assert.equal(await playground.ensureMounted(harness.document), harness.context);

    locationState.hash = "#recipe=skill&include=capability.cli";
    dispatchHashChange();
    const changed = await playground.ensureMounted(harness.document);
    assert.ok(changed);
    assert.deepEqual(changed.state.includes, ["capability.cli"]);
    assert.notEqual(changed, harness.context);

    locationState.hash = "#recipe=unknown";
    dispatchHashChange();
    assert.equal(await playground.ensureMounted(harness.document), null);
    assert.equal(harness.root.dataset.playgroundError, "INVALID_SELECTION");
  } finally {
    await unmount(harness);
  }
});