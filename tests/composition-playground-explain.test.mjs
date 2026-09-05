import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const core = require("../assets/javascripts/composition-playground.js");
const explain = require("../assets/javascripts/composition-playground-explain.js");
const fixturePath = new URL("./fixtures/composition-playground-v1-explain.json", import.meta.url);
const documentPath = new URL("../docs/composition-playground.md", import.meta.url);
const zensicalPath = new URL("../zensical.template.toml", import.meta.url);
const workerPath = new URL("../assets/service-worker.js", import.meta.url);

async function projection() {
  const raw = JSON.parse(await readFile(fixturePath, "utf8"));
  return core.validateProjection(raw);
}

test("provider provenance bits and dependency edges explain canonical selection", async () => {
  const value = await projection();
  const item = core.lookupCase(value, "skill", ["capability.cli"]);
  const groups = explain.componentGroups(value, item);
  const byRole = new Map(groups.map((group) => [group.role, group.components]));
  const capability = byRole.get("capability")[0];
  const foundation = byRole.get("foundation")[0];

  assert.equal(capability.id, "capability.cli");
  assert.equal(capability.version, 2);
  assert.deepEqual(capability.directDependencies, ["foundation.web"]);
  assert.deepEqual(capability.reasons, [{ kind: "explicit-include" }]);

  assert.equal(foundation.id, "foundation.web");
  assert.deepEqual(foundation.directDependencies, []);
  assert.deepEqual(foundation.reasons, [
    { kind: "dependency", from_component: "capability.cli" }
  ]);
  assert.match(explain.reasonText(foundation.reasons[0]), /capability\.cli/);
  assert.equal(
    foundation.sourceUrl,
    `https://github.com/TakashiSasaki/templates/blob/${"a".repeat(40)}/components/foundation.web/component.json`
  );
});

test("contracts, materials, ownership, and initial plan are rendered from projection inventories", async () => {
  const value = await projection();
  const item = core.lookupCase(value, "skill", ["capability.cli", "lifecycle.composition-state"]);

  assert.deepEqual(explain.contractsForCase(value, item).map((entry) => entry.id), ["cli-interface"]);
  const materials = explain.materialsForCase(value, item);
  assert.deepEqual(materials.map((entry) => entry.destination), [
    ".template-composition/lock.json",
    "CLI_INTERFACE.md",
    "README.md",
    "web/routes.json"
  ]);
  assert.deepEqual(new Set(materials.map((entry) => entry.ownership)), new Set(["generated", "managed", "seed"]));
  assert.equal(explain.planSummary(item), "Canonical empty-target initial plan: 4 create.");

  const tree = explain.materialTree(materials);
  assert.equal(tree.children.get("web").children.get("routes.json").material.component, "foundation.web");
});

test("dependency provenance without a provider edge fails closed before core exposure", async () => {
  const base = JSON.parse(await readFile(fixturePath, "utf8"));
  const projectionValue = core.validateProjection(base);
  const item = core.lookupCase(projectionValue, "skill", ["capability.cli"]);
  const inconsistent = JSON.parse(JSON.stringify(base));
  const outcome = inconsistent.outcomes.find((entry) => entry.index === item.outcome_id);
  outcome.dependency_edges = [];
  assert.throws(
    () => core.validateProjection(inconsistent),
    (error) => error instanceof core.ProjectionError && error.code === "MALFORMED_PROJECTION"
  );
});

test("reader document and runtime registration expose explainability without changing provider URL", async () => {
  const document = await readFile(documentPath, "utf8");
  const template = await readFile(zensicalPath, "utf8");
  const worker = await readFile(workerPath, "utf8");
  assert.match(document, /data-projection-url="\/composition\/playground\/composition-playground-v1\.json\.gz"/);
  for (const marker of [
    "data-playground-explain",
    "data-playground-groups",
    "data-playground-contracts",
    "data-playground-plan-summary",
    "data-playground-material-tree"
  ]) {
    assert.ok(document.includes(marker), marker);
  }
  const coreIndex = template.indexOf('"javascripts/composition-playground.js"');
  const explainIndex = template.indexOf('"javascripts/composition-playground-explain.js"');
  assert.ok(coreIndex >= 0 && explainIndex > coreIndex);
  assert.match(worker, /"\/javascripts\/composition-playground\.js"/);
  assert.match(worker, /"\/javascripts\/composition-playground-explain\.js"/);
});


test("explainability consumes the core validated shared runtime context", async () => {
  const source = await readFile(new URL("../assets/javascripts/composition-playground-explain.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /loadProjection\(/);
  assert.match(source, /ensureMounted/);
  assert.match(source, /subscribe/);
});

test("core validation rejects malformed explainability-consumed values", async () => {
  const base = JSON.parse(await readFile(fixturePath, "utf8"));
  for (const [label, mutate] of [
    ["component summary", (value) => { value.components[0].summary = null; }],
    ["contract purpose", (value) => { value.contracts[0].purpose = 4; }],
    ["material destination", (value) => { value.materials[0].destination = "../escape"; }],
    ["initial plan count", (value) => { value.outcomes[0].initial_plan.action_counts.create = "1"; }]
  ]) {
    const value = JSON.parse(JSON.stringify(base));
    mutate(value);
    assert.throws(
      () => core.validateProjection(value),
      (error) => error.code === "MALFORMED_PROJECTION",
      label
    );
  }
});
