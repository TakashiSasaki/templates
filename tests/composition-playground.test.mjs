import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { gzipSync } from "node:zlib";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");
const fixturePath = new URL("./fixtures/composition-playground-v1.json", import.meta.url);

async function fixture() {
  return JSON.parse(await readFile(fixturePath, "utf8"));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildProvenance(compositionRevision = "b".repeat(40)) {
  return {
    schema_version: 2,
    repository: "TakashiSasaki/templates",
    site_commit: "c".repeat(40),
    publication_commits: {
      composition: compositionRevision,
      policy: "d".repeat(40)
    }
  };
}

async function provenanceRichFixture() {
  const raw = await fixture();
  const cli = raw.components.find((component) => component.id === "capability.cli");
  cli.requires = ["foundation.web"];
  raw.components.push(
    {
      id: "foundation.web",
      role: "foundation",
      version: 1,
      summary: "Synthetic required foundation",
      requires: [],
      conflicts: [],
      contract_ids: [],
      material_declarations: [],
      source_path: "components/foundation.web/component.json"
    },
    {
      id: "capability.browser",
      role: "capability",
      version: 1,
      summary: "Synthetic recipe default",
      requires: [],
      conflicts: [],
      contract_ids: [],
      material_declarations: [],
      source_path: "components/capability.browser/component.json"
    }
  );
  const recipe = raw.recipes[0];
  recipe.required_components = ["foundation.web"];
  recipe.default_components = ["capability.browser"];
  raw.outcomes[0].resolved_components = ["artifact.skill", "foundation.web", "capability.browser"];
  raw.outcomes[0].dependency_edges = [];
  raw.outcomes[1].resolved_components = ["artifact.skill", "capability.cli", "foundation.web", "capability.browser"];
  raw.outcomes[1].dependency_edges = [[1, 2]];
  raw.outcomes[2].resolved_components = ["artifact.skill", "foundation.web", "capability.browser", "lifecycle.composition-state"];
  raw.outcomes[2].dependency_edges = [];
  raw.outcomes[3].resolved_components = ["artifact.skill", "capability.cli", "foundation.web", "capability.browser", "lifecycle.composition-state"];
  raw.outcomes[3].dependency_edges = [[1, 2]];
  recipe.cases[0].selection_reason_masks = [1, 2, 4];
  recipe.cases[1].selection_reason_masks = [1, 8, 18, 4];
  recipe.cases[2].selection_reason_masks = [1, 2, 4, 8];
  recipe.cases[3].selection_reason_masks = [1, 8, 18, 4, 8];
  return raw;
}

async function relationalFixture() {
  const raw = await provenanceRichFixture();
  const cli = raw.components.find((component) => component.id === "capability.cli");
  cli.contract_ids = [0];
  raw.contracts = [{
    index: 0,
    component: "capability.cli",
    id: "cli-interface",
    document: "CLI_INTERFACE.md",
    schema: "schemas/cli-interface.schema.json",
    document_schema_version: 1,
    purpose: "Describe the CLI interface"
  }];
  raw.materials = [
    { index: 0, component: "artifact.skill", destination: "README.md", ownership: "seed", sha256: "0".repeat(64) },
    { index: 1, component: "capability.cli", destination: "CLI_INTERFACE.md", ownership: "managed", sha256: "1".repeat(64) },
    { index: 2, component: "foundation.web", destination: "web/routes.json", ownership: "generated", sha256: "2".repeat(64) },
    { index: 3, component: "capability.browser", destination: "web/browser.json", ownership: "generated", sha256: "3".repeat(64) },
    { index: 4, component: "lifecycle.composition-state", destination: ".template-composition/lock.json", ownership: "generated", sha256: "4".repeat(64) }
  ];
  raw.outcomes[0].contract_ids = [];
  raw.outcomes[0].material_ids = [0, 2, 3];
  raw.outcomes[1].contract_ids = [0];
  raw.outcomes[1].material_ids = [0, 1, 2, 3];
  raw.outcomes[2].contract_ids = [];
  raw.outcomes[2].material_ids = [0, 2, 3, 4];
  raw.outcomes[3].contract_ids = [0];
  raw.outcomes[3].material_ids = [0, 1, 2, 3, 4];
  return raw;
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

function jsonResponse(value) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
}

function fakeRoot(name) {
  const status = { textContent: "" };
  const app = { hidden: true };
  const placeholder = {};
  return {
    name,
    isConnected: true,
    dataset: {
      projectionUrl: `/${name}-projection.json`,
      provenanceUrl: `/${name}-provenance.json`
    },
    status,
    app,
    querySelector(selector) {
      if (selector === "[data-playground-status]") return status;
      if (selector === "[data-playground-app]") return app;
      return placeholder;
    }
  };
}

function fakeDocument(root) {
  return {
    currentRoot: root,
    getElementById(id) {
      return id === "composition-playground" ? this.currentRoot : null;
    }
  };
}

test("supported v1 projection loads compact canonical case tables", async () => {
  const projection = playground.validateProjection(await fixture());
  assert.equal(projection.semanticRevision, "a".repeat(40));
  assert.equal(projection.projectionId, "composition-playground-v1");
  assert.equal(projection.recipeById.size, 1);
  assert.equal(projection.outcomeById.size, 4);
  assert.equal(projection.recipeById.get("skill").cases.length, 4);
  assert.deepEqual(playground.lookupCase(projection, "skill", ["capability.cli"]).resolved_components, [
    "artifact.skill",
    "capability.cli"
  ]);
});

test("gzip publication transport decodes to the same projection object", async () => {
  const raw = await fixture();
  assert.equal(typeof globalThis.DecompressionStream, "function");
  const compressed = gzipSync(Buffer.from(JSON.stringify(raw), "utf8"));
  const response = new Response(compressed, { status: 200 });
  assert.deepEqual(
    await playground.decodeProjectionResponse(response, "/composition/playground/composition-playground-v1.json.gz"),
    raw
  );
});

test("unsupported schema version fails clearly", async () => {
  const raw = await fixture();
  raw.schema_version = 2;
  assert.throws(
    () => playground.validateProjection(raw),
    (error) => error.code === "UNSUPPORTED_PROJECTION"
  );
});

test("malformed projection fails closed", async () => {
  const raw = await fixture();
  raw.source.revision = "not-a-full-sha";
  assert.throws(
    () => playground.validateProjection(raw),
    (error) => error.code === "MALFORMED_PROJECTION"
  );

  const inconsistent = await fixture();
  inconsistent.recipes[0].cases[1].selection_reason_masks = [1];
  assert.throws(
    () => playground.validateProjection(inconsistent),
    (error) => error.code === "MALFORMED_PROJECTION"
  );
});

test("selection provenance masks exactly match recipe, explicit selection, and dependency relations", async () => {
  const valid = await provenanceRichFixture();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const wrongArtifact = clone(valid);
  wrongArtifact.recipes[0].cases[1].selection_reason_masks[0] = 8;
  wrongArtifact.recipes[0].cases[1].selection_reason_masks[1] = 9;
  assert.throws(
    () => playground.validateProjection(wrongArtifact),
    (error) => error.code === "MALFORMED_PROJECTION",
    "artifact bit moved to optional component"
  );

  const wrongExplicit = clone(valid);
  wrongExplicit.recipes[0].cases[1].selection_reason_masks[0] |= playground.EXPECTED_REASON_BITS.explicit_include;
  assert.throws(
    () => playground.validateProjection(wrongExplicit),
    (error) => error.code === "MALFORMED_PROJECTION",
    "explicit include bit assigned to recipe artifact"
  );

  const wrongRequired = clone(valid);
  wrongRequired.recipes[0].cases[1].selection_reason_masks[0] |= playground.EXPECTED_REASON_BITS.recipe_required;
  assert.throws(
    () => playground.validateProjection(wrongRequired),
    (error) => error.code === "MALFORMED_PROJECTION",
    "required bit assigned to non-required component"
  );

  const wrongDefault = clone(valid);
  wrongDefault.recipes[0].cases[1].selection_reason_masks[2] |= playground.EXPECTED_REASON_BITS.recipe_default;
  assert.throws(
    () => playground.validateProjection(wrongDefault),
    (error) => error.code === "MALFORMED_PROJECTION",
    "default bit assigned to non-default component"
  );

  const extraBit = clone(valid);
  extraBit.recipes[0].cases[1].selection_reason_masks[3] |= playground.EXPECTED_REASON_BITS.recipe_required;
  assert.throws(
    () => playground.validateProjection(extraBit),
    (error) => error.code === "MALFORMED_PROJECTION",
    "extra provenance bit"
  );

  const missingExpectedBit = clone(valid);
  missingExpectedBit.recipes[0].cases[1].selection_reason_masks[2] = playground.EXPECTED_REASON_BITS.dependency;
  assert.throws(
    () => playground.validateProjection(missingExpectedBit),
    (error) => error.code === "MALFORMED_PROJECTION",
    "missing expected required bit"
  );
});

test("dependency edges and dependency provenance agree with published component metadata", async () => {
  const raw = await provenanceRichFixture();
  assert.doesNotThrow(() => playground.validateProjection(raw));

  const missingEdge = clone(raw);
  missingEdge.outcomes[1].dependency_edges = [];
  assert.throws(
    () => playground.validateProjection(missingEdge),
    (error) => error.code === "MALFORMED_PROJECTION",
    "dependency reason without incoming edge"
  );

  const falseEdge = clone(raw);
  falseEdge.components.find((component) => component.id === "capability.cli").requires = [];
  assert.throws(
    () => playground.validateProjection(falseEdge),
    (error) => error.code === "MALFORMED_PROJECTION",
    "edge not advertised by source component requires"
  );
});

test("contracts and materials have outcome-local ownership and registration integrity", async () => {
  const valid = await relationalFixture();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const unresolvedContract = clone(valid);
  unresolvedContract.outcomes[0].contract_ids = [0];
  assert.throws(
    () => playground.validateProjection(unresolvedContract),
    (error) => error.code === "MALFORMED_PROJECTION",
    "outcome contract owned by unresolved component"
  );

  const missingRegistration = clone(valid);
  missingRegistration.components.find((component) => component.id === "capability.cli").contract_ids = [];
  assert.throws(
    () => playground.validateProjection(missingRegistration),
    (error) => error.code === "MALFORMED_PROJECTION",
    "owning component missing contract registration"
  );

  const foreignRegistration = clone(valid);
  foreignRegistration.components.find((component) => component.id === "artifact.skill").contract_ids = [0];
  assert.throws(
    () => playground.validateProjection(foreignRegistration),
    (error) => error.code === "MALFORMED_PROJECTION",
    "component lists another component's contract"
  );

  const unresolvedMaterial = clone(valid);
  unresolvedMaterial.outcomes[0].material_ids.push(1);
  assert.throws(
    () => playground.validateProjection(unresolvedMaterial),
    (error) => error.code === "MALFORMED_PROJECTION",
    "material owned by unresolved component"
  );

  const duplicateDestination = clone(valid);
  duplicateDestination.materials.push({
    index: 5,
    component: "capability.cli",
    destination: "README.md",
    ownership: "managed",
    sha256: "5".repeat(64)
  });
  duplicateDestination.outcomes[1].material_ids.push(5);
  assert.throws(
    () => playground.validateProjection(duplicateDestination),
    (error) => error.code === "MALFORMED_PROJECTION",
    "two referenced materials share one destination"
  );

  const globalOnlyDuplicate = clone(valid);
  globalOnlyDuplicate.materials.push({
    index: 5,
    component: "capability.cli",
    destination: ".template-composition/lock.json",
    ownership: "managed",
    sha256: "5".repeat(64)
  });
  assert.doesNotThrow(
    () => playground.validateProjection(globalOnlyDuplicate),
    "destination uniqueness is outcome-local, not a broader global restriction"
  );
});

test("semantic source revision and published provider revision are distinct identities", async () => {
  const projection = playground.validateProjection(await fixture());
  const provenance = playground.validateBuildProvenance(buildProvenance());
  assert.equal(projection.semanticRevision, "a".repeat(40));
  assert.equal(provenance.providerRevision, "b".repeat(40));
  assert.notEqual(projection.semanticRevision, provenance.providerRevision);
});

test("malformed Site build provenance fails closed", () => {
  const missingComposition = buildProvenance();
  delete missingComposition.publication_commits.composition;
  assert.throws(
    () => playground.validateBuildProvenance(missingComposition),
    (error) => error.code === "MALFORMED_PROVENANCE"
  );

  const wrongSchema = buildProvenance();
  wrongSchema.schema_version = 1;
  assert.throws(
    () => playground.validateBuildProvenance(wrongSchema),
    (error) => error.code === "MALFORMED_PROVENANCE"
  );
});

test("selection and lookup key round trip uses projection inventory only", async () => {
  const projection = playground.validateProjection(await fixture());
  const recipe = projection.recipeById.get("skill");
  assert.equal(playground.selectionMask(recipe, []), 0);
  assert.equal(playground.selectionMask(recipe, ["capability.cli"]), 1);
  assert.equal(playground.caseKey(recipe, []), "skill:0");
  assert.equal(playground.caseKey(recipe, ["capability.cli"]), "skill:1");
  assert.equal(playground.caseKey(recipe, ["lifecycle.composition-state"]), "skill:2");
  assert.equal(playground.caseKey(recipe, ["lifecycle.composition-state", "capability.cli"]), "skill:3");
  assert.throws(
    () => playground.caseKey(recipe, ["capability.pwa"]),
    (error) => error.code === "INVALID_SELECTION"
  );
});

test("URL hash restores recipe and explicit includes and serializes canonically", async () => {
  const projection = playground.validateProjection(await fixture());
  const hash = playground.stateHash("skill", ["lifecycle.composition-state", "capability.cli"]);
  assert.equal(hash, "#recipe=skill&include=capability.cli&include=lifecycle.composition-state");
  assert.deepEqual(playground.parseHash(hash, projection), {
    recipeId: "skill",
    includes: ["capability.cli", "lifecycle.composition-state"]
  });
  assert.throws(
    () => playground.parseHash("#recipe=skill&include=capability.pwa", projection),
    (error) => error.code === "INVALID_SELECTION"
  );
});

test("canonical configuration is serialized from projection scope plus selected case", async () => {
  const projection = playground.validateProjection(await fixture());
  const item = playground.lookupCase(projection, "skill", ["capability.cli"]);
  const rendered = playground.configurationText(item);
  assert.deepEqual(JSON.parse(rendered), item.configuration);
  assert.deepEqual(item.configuration, {
    schema_version: 1,
    recipe: "skill",
    components: { include: ["capability.cli"], exclude: [] },
    parameters: {}
  });
});

test("projection and provenance availability errors map to explicit UI status", () => {
  assert.match(
    playground.statusForError(new playground.ProjectionError("PROJECTION_UNAVAILABLE", "HTTP 404")),
    /not available/
  );
  assert.match(
    playground.statusForError(new playground.ProjectionError("PROVENANCE_UNAVAILABLE", "HTTP 404")),
    /provenance required/
  );
  assert.match(
    playground.statusForError(new playground.ProjectionError("MALFORMED_PROVENANCE", "bad")),
    /malformed/
  );
});

test("all Site-consumed explainability fields are validated before exposure", async () => {
  const base = await fixture();
  base.contracts = [{
    index: 0, component: "artifact.skill", id: "artifact-contract",
    document: "ARTIFACT.md", schema: "schemas/artifact.schema.json",
    document_schema_version: 1, purpose: "Describe the artifact"
  }];
  base.components[0].contract_ids = [0];
  base.materials = [{
    index: 0, component: "artifact.skill", destination: "README.md",
    ownership: "seed", sha256: "0".repeat(64)
  }];
  base.outcomes[0].contract_ids = [0];
  base.outcomes[0].material_ids = [0];
  assert.doesNotThrow(() => playground.validateProjection(base));

  for (const [label, mutate] of [
    ["component role", (value) => { value.components[0].role = "unknown"; }],
    ["component summary", (value) => { value.components[0].summary = 7; }],
    ["recipe source", (value) => { value.recipes[0].source_path = "../recipe.json"; }],
    ["contract purpose", (value) => { value.contracts[0].purpose = null; }],
    ["material destination", (value) => { delete value.materials[0].destination; }],
    ["material ownership", (value) => { value.materials[0].ownership = "unknown"; }],
    ["initial plan", (value) => { value.outcomes[0].initial_plan.action_counts.create = "1"; }]
  ]) {
    const value = clone(base);
    mutate(value);
    assert.throws(
      () => playground.validateProjection(value),
      (error) => error.code === "MALFORMED_PROJECTION",
      label
    );
  }
});

test("stale successful mount cannot publish over a replacement generation", async () => {
  const originalFetch = globalThis.fetch;
  const rootA = fakeRoot("a-success");
  const rootB = fakeRoot("b-current");
  const document = fakeDocument(rootA);
  const projectionRequest = deferred();
  const provenanceRequest = deferred();
  const events = [];
  const unsubscribe = playground.subscribe((event) => events.push(event));
  globalThis.fetch = (url) => {
    if (url === "/a-success-projection.json") return projectionRequest.promise;
    if (url === "/a-success-provenance.json") return provenanceRequest.promise;
    if (url === "/b-current-projection.json") return Promise.reject(new Error("replacement failure"));
    if (url === "/b-current-provenance.json") return Promise.resolve(jsonResponse(buildProvenance("e".repeat(40))));
    return Promise.reject(new Error(`unexpected URL ${url}`));
  };
  try {
    const stalePromise = playground.ensureMounted(document);
    document.currentRoot = rootB;
    const currentPromise = playground.ensureMounted(document);
    assert.equal(await currentPromise, null);
    const currentError = events.find((event) => event.type === "error");
    assert.equal(currentError?.root, rootB);
    assert.equal(currentError?.error.message, "replacement failure");

    projectionRequest.resolve(jsonResponse(await fixture()));
    provenanceRequest.resolve(jsonResponse(buildProvenance()));
    assert.equal(await stalePromise, null);
    assert.equal(events.filter((event) => event.type === "error").length, 1);
    assert.equal(events.filter((event) => event.type === "ready").length, 0);
    assert.equal(events.find((event) => event.type === "error")?.root, rootB);
  } finally {
    document.currentRoot = null;
    await playground.ensureMounted(document);
    unsubscribe();
    globalThis.fetch = originalFetch;
  }
});

test("stale failed mount cannot overwrite a replacement generation error", async () => {
  const originalFetch = globalThis.fetch;
  const rootA = fakeRoot("a-failure");
  const rootB = fakeRoot("b-current-failure");
  const document = fakeDocument(rootA);
  const staleProjectionRequest = deferred();
  const events = [];
  const unsubscribe = playground.subscribe((event) => events.push(event));
  globalThis.fetch = (url) => {
    if (url === "/a-failure-projection.json") return staleProjectionRequest.promise;
    if (url === "/a-failure-provenance.json") return Promise.resolve(jsonResponse(buildProvenance()));
    if (url === "/b-current-failure-projection.json") return Promise.reject(new Error("current generation failure"));
    if (url === "/b-current-failure-provenance.json") return Promise.resolve(jsonResponse(buildProvenance("e".repeat(40))));
    return Promise.reject(new Error(`unexpected URL ${url}`));
  };
  try {
    const stalePromise = playground.ensureMounted(document);
    document.currentRoot = rootB;
    const currentPromise = playground.ensureMounted(document);
    assert.equal(await currentPromise, null);
    assert.equal(events.filter((event) => event.type === "error").length, 1);
    assert.equal(events.find((event) => event.type === "error")?.error.message, "current generation failure");

    staleProjectionRequest.reject(new Error("stale generation failure"));
    assert.equal(await stalePromise, null);
    const errors = events.filter((event) => event.type === "error");
    assert.equal(errors.length, 1);
    assert.equal(errors[0].root, rootB);
    assert.equal(errors[0].error.message, "current generation failure");
  } finally {
    document.currentRoot = null;
    await playground.ensureMounted(document);
    unsubscribe();
    globalThis.fetch = originalFetch;
  }
});
