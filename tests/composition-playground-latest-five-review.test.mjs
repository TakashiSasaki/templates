import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildProvenance(siteRevision = "c".repeat(40)) {
  return {
    schema_version: 2,
    repository: "TakashiSasaki/templates",
    site_commit: siteRevision,
    publication_commits: {
      composition: "b".repeat(40),
      policy: "d".repeat(40),
    },
  };
}

function projectionWithMaterials() {
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
    materials: [
      {
        index: 0,
        component: "artifact.skill",
        destination: "SKILL.md",
        ownership: "managed",
        sha256: "1".repeat(64),
      },
      {
        index: 1,
        component: "capability.cli",
        destination: "bin/tool.sh",
        ownership: "generated",
        sha256: "2".repeat(64),
      },
    ],
    outcomes: [
      {
        index: 0,
        resolved_components: ["artifact.skill"],
        dependency_edges: [],
        contract_ids: [],
        material_ids: [0],
        initial_plan: { action_counts: { create: 1 }, conflict_count: 0 },
      },
      {
        index: 1,
        resolved_components: ["artifact.skill", "capability.cli"],
        dependency_edges: [],
        contract_ids: [],
        material_ids: [0, 1],
        initial_plan: { action_counts: { create: 2 }, conflict_count: 0 },
      },
    ],
  };
}

class FakeNode {
  constructor(tagName = "div", ownerDocument = null) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
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
  get firstChild() { return this.children[0] || null; }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    if (this.tagName === "SELECT" && child.tagName === "OPTION" && child.selected) this.value = child.value;
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
  focus() {
    if (this.ownerDocument) this.ownerDocument.activeElement = this;
  }
  querySelectorAll(selector) {
    const matches = [];
    const walk = (node) => {
      for (const child of node.children) {
        const checkbox = child.tagName === "INPUT" && child.type === "checkbox";
        if (
          (selector === "input[type=checkbox]" && checkbox) ||
          (selector === "input[type=checkbox]:checked" && checkbox && child.checked)
        ) matches.push(child);
        walk(child);
      }
    };
    walk(this);
    return matches;
  }
}

function fakeHarness(name, metaRevision = "c".repeat(40)) {
  const selectors = new Map();
  const document = {
    activeElement: null,
    currentRoot: null,
    createElement(tagName) { return new FakeNode(tagName, this); },
    createTextNode(text) {
      const node = new FakeNode("#text", this);
      node.textContent = text;
      return node;
    },
    getElementById(id) { return id === "composition-playground" ? this.currentRoot : null; },
    querySelector(selector) {
      if (selector !== 'meta[name="templates-site-revision"]') return null;
      return metaRevision === null ? null : { content: metaRevision };
    },
  };
  const make = (tag) => new FakeNode(tag, document);
  const status = make("p");
  const app = make("div"); app.hidden = true;
  const recipe = make("select");
  const optionals = make("div");
  const validity = make("p");
  const semanticRevision = make("code");
  const providerRevision = make("code");
  const projectionId = make("code");
  const resolved = make("ul");
  const config = make("pre");
  const copy = make("button");
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
  const root = make("div");
  root.dataset.projectionUrl = `/${name}-projection.json`;
  root.dataset.provenanceUrl = `/${name}-provenance.json`;
  root.querySelector = (selector) => selectors.get(selector) || null;
  document.currentRoot = root;
  return { document, root, status, app, recipe, optionals, config };
}

const originalGlobals = {
  fetch: globalThis.fetch,
  location: globalThis.location,
  history: globalThis.history,
  navigator: globalThis.navigator,
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
  value: { clipboard: { writeText: async () => {} } },
});

async function cleanup(document) {
  document.currentRoot = null;
  await playground.ensureMounted(document);
}

function assertMalformed(value, message) {
  assert.throws(
    () => playground.validateProjection(value),
    (error) => error.code === "MALFORMED_PROJECTION",
    message,
  );
}

test("resolved owners require their complete published material set without ordering significance", () => {
  const valid = projectionWithMaterials();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const omitted = clone(valid);
  omitted.outcomes[1].material_ids = [0];
  omitted.outcomes[1].initial_plan.action_counts.create = 1;
  assertMalformed(omitted, "omitting a material while its owner remains resolved must fail");

  const reordered = clone(valid);
  reordered.outcomes[1].material_ids = [1, 0];
  assert.doesNotThrow(() => playground.validateProjection(reordered));

  const unresolvedOwner = clone(valid);
  unresolvedOwner.outcomes[0].material_ids = [0, 1];
  unresolvedOwner.outcomes[0].initial_plan.action_counts.create = 2;
  assertMalformed(unresolvedOwner, "a material owned by an unresolved component must fail");

  const noPublishedMaterial = clone(valid);
  noPublishedMaterial.materials = noPublishedMaterial.materials.filter((material) => material.component !== "capability.cli");
  noPublishedMaterial.outcomes[1].material_ids = [0];
  noPublishedMaterial.outcomes[1].initial_plan.action_counts.create = 1;
  assert.doesNotThrow(() => playground.validateProjection(noPublishedMaterial));
});

test("material destinations reject only complete .git path segments", () => {
  for (const destination of [".git/config", "subdir/.git/HEAD"]) {
    const value = projectionWithMaterials();
    value.materials[0].destination = destination;
    assertMalformed(value, `${destination} must be rejected`);
  }
  for (const destination of [".github/workflows/test.yml", ".gitignore", "git/config", "something.git/HEAD", "nested/material.txt"]) {
    const value = projectionWithMaterials();
    value.materials[0].destination = destination;
    assert.doesNotThrow(() => playground.validateProjection(value), destination);
  }
});

test("Site document revision is separately bound to structurally validated build provenance", () => {
  const provenance = playground.validateBuildProvenance(buildProvenance());
  const matching = { querySelector: () => ({ content: "c".repeat(40) }) };
  assert.equal(playground.validateDocumentBuildProvenance(matching, provenance), provenance);

  const mismatch = { querySelector: () => ({ content: "e".repeat(40) }) };
  assert.throws(
    () => playground.validateDocumentBuildProvenance(mismatch, provenance),
    (error) => error.code === "MALFORMED_PROVENANCE" && /does not match/.test(error.message),
  );

  const malformed = { querySelector: () => ({ content: "not-a-revision" }) };
  assert.throws(
    () => playground.validateDocumentBuildProvenance(malformed, provenance),
    (error) => error.code === "MALFORMED_PROVENANCE",
  );

  const projection = playground.validateProjection(projectionWithMaterials());
  assert.equal(projection.semanticRevision, "a".repeat(40));
  assert.equal(provenance.providerRevision, "b".repeat(40));
  assert.notEqual(projection.semanticRevision, provenance.providerRevision);
});

test("user checkbox changes restore focus to the corresponding rerendered checkbox", async () => {
  const harness = fakeHarness("focus");
  const projection = projectionWithMaterials();
  globalThis.fetch = async (url) => {
    if (url === "/focus-projection.json") return new Response(JSON.stringify(projection), { status: 200 });
    if (url === "/focus-provenance.json") return new Response(JSON.stringify(buildProvenance()), { status: 200 });
    throw new Error(`unexpected URL ${url}`);
  };
  try {
    const initial = await playground.ensureMounted(harness.document);
    assert.ok(initial);
    const first = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    first.focus();
    first.checked = true;
    first.dispatch("change");
    const rerendered = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    assert.equal(harness.document.activeElement, rerendered);
    assert.equal(rerendered.value, "capability.cli");
    assert.equal((await playground.ensureMounted(harness.document)).state.includes[0], "capability.cli");

    rerendered.checked = false;
    rerendered.dispatch("change");
    const twiceRendered = harness.optionals.querySelectorAll("input[type=checkbox]")[0];
    assert.equal(harness.document.activeElement, twiceRendered);
    assert.equal(twiceRendered.value, "capability.cli");
    assert.deepEqual((await playground.ensureMounted(harness.document)).state.includes, []);
  } finally {
    await cleanup(harness.document);
  }
});

test("projection availability failure retries once on the same root and concurrent retries share one flight", async () => {
  const harness = fakeHarness("projection-retry");
  const projection = projectionWithMaterials();
  let projectionAvailable = false;
  let projectionRequests = 0;
  globalThis.fetch = async (url) => {
    if (url === "/projection-retry-projection.json") {
      projectionRequests += 1;
      if (!projectionAvailable) return new Response("offline", { status: 503 });
      return new Response(JSON.stringify(projection), { status: 200 });
    }
    if (url === "/projection-retry-provenance.json") return new Response(JSON.stringify(buildProvenance()), { status: 200 });
    throw new Error(`unexpected URL ${url}`);
  };
  try {
    assert.equal(await playground.ensureMounted(harness.document), null);
    assert.equal(harness.root.dataset.playgroundError, "PROJECTION_UNAVAILABLE");
    projectionAvailable = true;
    const firstRetry = playground.ensureMounted(harness.document);
    const concurrentRetry = playground.ensureMounted(harness.document);
    assert.equal(firstRetry, concurrentRetry);
    const context = await firstRetry;
    assert.ok(context);
    assert.equal(projectionRequests, 2);
    assert.equal(await playground.ensureMounted(harness.document), context);
    assert.equal(projectionRequests, 2);
  } finally {
    await cleanup(harness.document);
  }
});

test("provenance availability failure retries on the same root", async () => {
  const harness = fakeHarness("provenance-retry");
  const projection = projectionWithMaterials();
  let provenanceAvailable = false;
  let projectionRequests = 0;
  let provenanceRequests = 0;
  globalThis.fetch = async (url) => {
    if (url === "/provenance-retry-projection.json") {
      projectionRequests += 1;
      return new Response(JSON.stringify(projection), { status: 200 });
    }
    if (url === "/provenance-retry-provenance.json") {
      provenanceRequests += 1;
      if (!provenanceAvailable) return new Response("offline", { status: 503 });
      return new Response(JSON.stringify(buildProvenance()), { status: 200 });
    }
    throw new Error(`unexpected URL ${url}`);
  };
  try {
    assert.equal(await playground.ensureMounted(harness.document), null);
    assert.equal(harness.root.dataset.playgroundError, "PROVENANCE_UNAVAILABLE");
    provenanceAvailable = true;
    assert.ok(await playground.ensureMounted(harness.document));
    assert.equal(projectionRequests, 2);
    assert.equal(provenanceRequests, 2);
  } finally {
    await cleanup(harness.document);
  }
});

test("semantic projection errors do not become automatic same-root retries", async () => {
  for (const [label, mutate] of [
    ["unsupported", (value) => { value.schema_version = 99; }],
    ["malformed", (value) => { value.outcomes = []; }],
  ]) {
    const harness = fakeHarness(`nonretry-${label}`);
    const invalidProjection = projectionWithMaterials();
    mutate(invalidProjection);
    let projectionRequests = 0;
    globalThis.fetch = async (url) => {
      if (url === `/nonretry-${label}-projection.json`) {
        projectionRequests += 1;
        return new Response(JSON.stringify(invalidProjection), { status: 200 });
      }
      if (url === `/nonretry-${label}-provenance.json`) return new Response(JSON.stringify(buildProvenance()), { status: 200 });
      throw new Error(`unexpected URL ${url}`);
    };
    try {
      assert.equal(await playground.ensureMounted(harness.document), null);
      assert.equal(await playground.ensureMounted(harness.document), null);
      assert.equal(projectionRequests, 1, `${label} projection must not retry automatically`);
    } finally {
      await cleanup(harness.document);
    }
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