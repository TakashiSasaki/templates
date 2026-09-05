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
    const all = [];
    const walk = (node) => {
      for (const child of node.children) {
        const isCheckbox = child.tagName === "INPUT" && child.type === "checkbox";
        if (
          (selector === "input[type=checkbox]" && isCheckbox) ||
          (selector === "input[type=checkbox]:checked" && isCheckbox && child.checked)
        ) {
          all.push(child);
        }
        walk(child);
      }
    };
    walk(this);
    return all;
  }
}

const originalGlobals = {
  fetch: globalThis.fetch,
  location: globalThis.location,
  history: globalThis.history,
  navigator: globalThis.navigator,
};

const locationState = { pathname: "/playground/", search: "", hash: "" };
Object.defineProperty(globalThis, "location", { configurable: true, writable: true, value: locationState });
Object.defineProperty(globalThis, "history", {
  configurable: true,
  writable: true,
  value: {
    replaceState(_state, _title, url) { locationState.hash = new URL(url, "https://example.test").hash; },
    pushState(_state, _title, url) { locationState.hash = new URL(url, "https://example.test").hash; },
  },
});
const navigatorState = { clipboard: { writeText: async () => {} } };
Object.defineProperty(globalThis, "navigator", { configurable: true, writable: true, value: navigatorState });

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildProvenance() {
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

function simpleProjection() {
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
        id: "artifact.skill", role: "artifact", version: 1, summary: "Skill artifact",
        requires: [], conflicts: [], contract_ids: [], material_declarations: [],
        source_path: "components/artifact.skill/component.json",
      },
      {
        id: "capability.cli", role: "capability", version: 1, summary: "CLI capability",
        requires: [], conflicts: [], contract_ids: [], material_declarations: [],
        source_path: "components/capability.cli/component.json",
      },
    ],
    contracts: [],
    materials: [],
    outcomes: [
      {
        index: 0, resolved_components: ["artifact.skill"], dependency_edges: [], contract_ids: [], material_ids: [],
        initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
      },
      {
        index: 1, resolved_components: ["artifact.skill", "capability.cli"], dependency_edges: [], contract_ids: [], material_ids: [],
        initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
      },
    ],
  };
}

function relationalProjection() {
  const raw = simpleProjection();
  raw.recipes[0].optional_components = [];
  raw.recipes[0].case_count = 1;
  raw.recipes[0].cases = [{
    valid: true,
    error: null,
    outcome_id: 0,
    selection_reason_masks: [1, 16, 16],
  }];
  raw.components[0].requires = ["capability.cli"];
  raw.components[1].requires = ["foundation.web"];
  raw.components[1].contract_ids = [0];
  raw.components.push({
    id: "foundation.web", role: "foundation", version: 1, summary: "Web foundation",
    requires: [], conflicts: [], contract_ids: [], material_declarations: [],
    source_path: "components/foundation.web/component.json",
  });
  raw.contracts = [{
    index: 0,
    component: "capability.cli",
    id: "cli-interface",
    document: "CLI_INTERFACE.md",
    schema: "schemas/cli-interface.schema.json",
    document_schema_version: 1,
    purpose: "Describe the CLI contract",
  }];
  raw.outcomes = [{
    index: 0,
    resolved_components: ["artifact.skill", "capability.cli", "foundation.web"],
    dependency_edges: [[0, 1], [1, 2]],
    contract_ids: [0],
    material_ids: [],
    initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
  }];
  return raw;
}

function fakeDocument(root) {
  return {
    createElement(tagName) { return new FakeNode(tagName); },
    createTextNode(text) { const node = new FakeNode("#text"); node.textContent = text; return node; },
    getElementById(id) { return id === "composition-playground" ? this.currentRoot : null; },
    currentRoot: root,
  };
}

function fakeRoot(name = "root") {
  const selectors = new Map();
  const status = new FakeNode("p");
  const app = new FakeNode("div"); app.hidden = true;
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
  return { root, status, app, recipe, optionals, copy };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolveValue, rejectValue) => {
    resolve = resolveValue;
    reject = rejectValue;
  });
  return { promise, resolve, reject };
}

async function mountClipboardHarness(name = "clipboard") {
  const nodes = fakeRoot(name);
  const document = fakeDocument(nodes.root);
  const projection = simpleProjection();
  globalThis.fetch = async (url) => {
    if (url === `/${name}-projection.json`) return new Response(JSON.stringify(projection), { status: 200 });
    if (url === `/${name}-provenance.json`) return new Response(JSON.stringify(buildProvenance()), { status: 200 });
    throw new Error(`unexpected URL ${url}`);
  };
  locationState.hash = "#recipe=skill";
  const context = await playground.ensureMounted(document);
  assert.ok(context);
  return { ...nodes, document };
}

async function cleanupHarness(document) {
  document.currentRoot = null;
  await playground.ensureMounted(document);
}

test("build provenance requires the exact Site v2 record and provider set", () => {
  const valid = buildProvenance();
  const result = playground.validateBuildProvenance(valid);
  assert.equal(result.siteRevision, "c".repeat(40));
  assert.equal(result.providerRevision, "b".repeat(40));
  assert.equal(result.policyRevision, "d".repeat(40));

  const invalids = [
    ["missing site_commit", (value) => { delete value.site_commit; }],
    ["malformed site_commit", (value) => { value.site_commit = "C".repeat(40); }],
    ["missing composition", (value) => { delete value.publication_commits.composition; }],
    ["malformed composition", (value) => { value.publication_commits.composition = "short"; }],
    ["missing policy", (value) => { delete value.publication_commits.policy; }],
    ["malformed policy", (value) => { value.publication_commits.policy = "D".repeat(40); }],
    ["extra provider", (value) => { value.publication_commits.other = "e".repeat(40); }],
    ["unexpected top-level field", (value) => { value.extra = true; }],
  ];
  for (const [label, mutate] of invalids) {
    const value = clone(valid);
    mutate(value);
    assert.throws(
      () => playground.validateBuildProvenance(value),
      (error) => error.code === "MALFORMED_PROVENANCE",
      label,
    );
  }
});

test("ordinary fragments are distinct from canonical Playground state", () => {
  const projection = playground.validateProjection(simpleProjection());
  assert.deepEqual(playground.parseHash("", projection), { recipeId: "skill", includes: [] });
  assert.deepEqual(playground.parseHash("#v1-scope", projection), { recipeId: "skill", includes: [] });
  const canonical = playground.stateHash("skill", ["capability.cli"]);
  assert.equal(canonical, "#recipe=skill&include=capability.cli");
  assert.deepEqual(playground.parseHash(canonical, projection), { recipeId: "skill", includes: ["capability.cli"] });
  assert.throws(
    () => playground.parseHash("#recipe=unknown", projection),
    (error) => error.code === "INVALID_SELECTION",
  );
  assert.throws(
    () => playground.parseHash("#recipe=skill&unexpected=1", projection),
    (error) => error.code === "INVALID_SELECTION",
  );
});

test("dependency_edges exactly represent every declared requires relation in an outcome", () => {
  const valid = relationalProjection();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const targetMissing = clone(valid);
  targetMissing.outcomes[0].resolved_components = ["artifact.skill", "capability.cli"];
  targetMissing.outcomes[0].dependency_edges = [[0, 1]];
  targetMissing.recipes[0].cases[0].selection_reason_masks = [1, 16];
  assert.throws(
    () => playground.validateProjection(targetMissing),
    (error) => error.code === "MALFORMED_PROJECTION",
    "required target missing from resolved_components",
  );

  const edgeMissing = clone(valid);
  edgeMissing.outcomes[0].dependency_edges = [[0, 1]];
  assert.throws(
    () => playground.validateProjection(edgeMissing),
    (error) => error.code === "MALFORMED_PROJECTION",
    "required target still resolved but edge omitted",
  );

  const spuriousEdge = clone(valid);
  spuriousEdge.outcomes[0].dependency_edges.push([2, 0]);
  assert.throws(
    () => playground.validateProjection(spuriousEdge),
    (error) => error.code === "MALFORMED_PROJECTION",
    "spurious edge absent from source requires",
  );
});

test("outcome contract_ids equal the union advertised by resolved components", () => {
  const valid = relationalProjection();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const omitted = clone(valid);
  omitted.outcomes[0].contract_ids = [];
  assert.throws(
    () => playground.validateProjection(omitted),
    (error) => error.code === "MALFORMED_PROJECTION",
    "resolved component advertises a contract omitted by outcome",
  );

  const unresolvedOwner = clone(valid);
  unresolvedOwner.components.push({
    id: "capability.extra", role: "capability", version: 1, summary: "Extra capability",
    requires: [], conflicts: [], contract_ids: [1], material_declarations: [],
    source_path: "components/capability.extra/component.json",
  });
  unresolvedOwner.contracts.push({
    index: 1, component: "capability.extra", id: "extra-contract", document: "EXTRA.md",
    schema: "schemas/extra.schema.json", document_schema_version: 1, purpose: "Extra contract",
  });
  unresolvedOwner.outcomes[0].contract_ids.push(1);
  assert.throws(
    () => playground.validateProjection(unresolvedOwner),
    (error) => error.code === "MALFORMED_PROJECTION",
    "outcome lists a contract owned by an unresolved component",
  );

  const foreign = clone(valid);
  foreign.components[0].contract_ids = [0];
  assert.throws(
    () => playground.validateProjection(foreign),
    (error) => error.code === "MALFORMED_PROJECTION",
    "component advertises a foreign contract",
  );
});

test("component namespace agrees with role and recipe artifact retains artifact identity", () => {
  const valid = relationalProjection();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const artifactMismatch = clone(valid);
  artifactMismatch.components[0].role = "capability";
  assert.throws(() => playground.validateProjection(artifactMismatch), (error) => error.code === "MALFORMED_PROJECTION");

  const capabilityMismatch = clone(valid);
  capabilityMismatch.components[1].role = "artifact";
  assert.throws(() => playground.validateProjection(capabilityMismatch), (error) => error.code === "MALFORMED_PROJECTION");

  const nonArtifactRecipe = clone(valid);
  nonArtifactRecipe.recipes[0].artifact = "capability.cli";
  assert.throws(() => playground.validateProjection(nonArtifactRecipe), (error) => error.code === "MALFORMED_PROJECTION");
});

test("stale clipboard success is ignored after selection changes", async () => {
  const pending = deferred();
  navigatorState.clipboard.writeText = () => pending.promise;
  const harness = await mountClipboardHarness("copy-stale-success");
  try {
    harness.copy.dispatch("click");
    const checkbox = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    checkbox.checked = true;
    checkbox.dispatch("change");
    const statusBefore = harness.status.textContent;
    pending.resolve();
    await pending.promise;
    await Promise.resolve();
    assert.equal(harness.status.textContent, statusBefore);
    assert.notEqual(harness.status.textContent, playground.labels.copied);
  } finally {
    await cleanupHarness(harness.document);
  }
});

test("stale clipboard failure is ignored after selection changes", async () => {
  const pending = deferred();
  navigatorState.clipboard.writeText = () => pending.promise;
  const harness = await mountClipboardHarness("copy-stale-failure");
  try {
    harness.copy.dispatch("click");
    const checkbox = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    checkbox.checked = true;
    checkbox.dispatch("change");
    const statusBefore = harness.status.textContent;
    pending.reject(new Error("clipboard denied"));
    await pending.promise.catch(() => {});
    await Promise.resolve();
    assert.equal(harness.status.textContent, statusBefore);
    assert.notEqual(harness.status.textContent, playground.labels.copyFailed);
  } finally {
    await cleanupHarness(harness.document);
  }
});

test("current clipboard success still publishes feedback", async () => {
  const pending = deferred();
  navigatorState.clipboard.writeText = () => pending.promise;
  const harness = await mountClipboardHarness("copy-current-success");
  try {
    harness.copy.dispatch("click");
    pending.resolve();
    await pending.promise;
    await Promise.resolve();
    assert.equal(harness.status.textContent, playground.labels.copied);
  } finally {
    await cleanupHarness(harness.document);
  }
});

test.after(() => {
  Object.defineProperty(globalThis, "fetch", { configurable: true, writable: true, value: originalGlobals.fetch });
  if (originalGlobals.location === undefined) delete globalThis.location;
  else Object.defineProperty(globalThis, "location", { configurable: true, writable: true, value: originalGlobals.location });
  if (originalGlobals.history === undefined) delete globalThis.history;
  else Object.defineProperty(globalThis, "history", { configurable: true, writable: true, value: originalGlobals.history });
  Object.defineProperty(globalThis, "navigator", { configurable: true, writable: true, value: originalGlobals.navigator });
});
