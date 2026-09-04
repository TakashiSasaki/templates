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
