import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");
const fixturePath = new URL("./fixtures/composition-playground-v1.json", import.meta.url);

async function fixture() {
  return JSON.parse(await readFile(fixturePath, "utf8"));
}

test("supported v1 projection loads and indexes canonical cases", async () => {
  const projection = playground.validateProjection(await fixture());
  assert.equal(projection.sourceRevision, "a".repeat(40));
  assert.equal(projection.recipeById.size, 1);
  assert.equal(projection.caseByKey.size, 4);
  assert.deepEqual(playground.lookupCase(projection, "skill", ["capability.cli"]).resolved_components, [
    "artifact.skill",
    "capability.cli"
  ]);
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
});

test("mismatched expected source revision fails closed", async () => {
  const raw = await fixture();
  assert.throws(
    () => playground.validateProjection(raw, { expectedRevision: "b".repeat(40) }),
    (error) => error.code === "SOURCE_REVISION_MISMATCH"
  );
});

test("selection and lookup key round trip uses projection inventory only", async () => {
  const projection = playground.validateProjection(await fixture());
  const recipe = projection.recipeById.get("skill");
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

test("canonical configuration is serialized from the selected projection case", async () => {
  const projection = playground.validateProjection(await fixture());
  const item = playground.lookupCase(projection, "skill", ["capability.cli"]);
  const rendered = playground.configurationText(item);
  assert.deepEqual(JSON.parse(rendered), item.configuration);
  assert.deepEqual(item.configuration.components.exclude, []);
  assert.deepEqual(item.configuration.parameters, {});
});

test("projection availability and compatibility errors map to explicit UI status", () => {
  assert.match(
    playground.statusForError(new playground.ProjectionError("PROJECTION_UNAVAILABLE", "HTTP 404")),
    /not available/
  );
  assert.match(
    playground.statusForError(new playground.ProjectionError("SOURCE_REVISION_MISMATCH", "stale")),
    /incompatible/
  );
});
