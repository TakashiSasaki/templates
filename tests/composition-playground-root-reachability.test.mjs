import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");
const fixture = JSON.parse(
  fs.readFileSync(new URL("./fixtures/composition-playground-v1.json", import.meta.url), "utf8")
);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function componentRecord(id, requires = []) {
  const role = id.slice(0, id.indexOf("."));
  return {
    id,
    role,
    version: 1,
    summary: `Synthetic ${id}`,
    requires: requires.slice(),
    conflicts: [],
    contract_ids: [],
    material_declarations: [],
    source_path: `components/${id}/component.json`,
  };
}

function upsertComponent(value, id, requires = []) {
  const existing = value.components.find((component) => component.id === id);
  if (existing) {
    existing.requires = requires.slice();
    return;
  }
  value.components.push(componentRecord(id, requires));
}

function singleCaseProjection({ required = [], defaults = [], resolved, edges, masks, requires = {} }) {
  const value = clone(fixture);
  const recipe = value.recipes[0];
  recipe.required_components = required.slice();
  recipe.default_components = defaults.slice();
  recipe.optional_components = [];
  recipe.case_count = 1;
  recipe.cases = [{ valid: true, error: null, outcome_id: 0, selection_reason_masks: masks.slice() }];
  value.outcomes = [{
    index: 0,
    resolved_components: resolved.slice(),
    dependency_edges: edges.map((edge) => edge.slice()),
    contract_ids: [],
    material_ids: [],
    initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
  }];
  for (const component of value.components) component.requires = [];
  for (const [id, targets] of Object.entries(requires)) upsertComponent(value, id, targets);
  for (const id of resolved) upsertComponent(value, id, requires[id] || []);
  return value;
}

test("dependency-only two-node cycle without a directly selected root is rejected", () => {
  const value = singleCaseProjection({
    resolved: ["artifact.skill", "foundation.a", "foundation.b"],
    edges: [[1, 2], [2, 1]],
    masks: [1, 16, 16],
    requires: {
      "foundation.a": ["foundation.b"],
      "foundation.b": ["foundation.a"],
    },
  });
  assert.throws(
    () => playground.validateProjection(value),
    (error) => error.code === "MALFORMED_PROJECTION" && /reachable/.test(error.message)
  );
});

test("longer dependency-only cycle with valid incoming edges is rejected when unreachable", () => {
  const value = singleCaseProjection({
    resolved: ["artifact.skill", "foundation.a", "foundation.b", "foundation.c"],
    edges: [[1, 2], [2, 3], [3, 1]],
    masks: [1, 16, 16, 16],
    requires: {
      "foundation.a": ["foundation.b"],
      "foundation.b": ["foundation.c"],
      "foundation.c": ["foundation.a"],
    },
  });
  assert.throws(
    () => playground.validateProjection(value),
    (error) => error.code === "MALFORMED_PROJECTION" && /reachable/.test(error.message)
  );
});

test("dependency chain reachable from the recipe artifact is accepted", () => {
  const value = singleCaseProjection({
    resolved: ["artifact.skill", "foundation.a", "foundation.b"],
    edges: [[0, 1], [1, 2]],
    masks: [1, 16, 16],
    requires: {
      "artifact.skill": ["foundation.a"],
      "foundation.a": ["foundation.b"],
    },
  });
  assert.doesNotThrow(() => playground.validateProjection(value));
});

test("dependency chains reachable from required and default roots are accepted", () => {
  const required = singleCaseProjection({
    required: ["capability.cli"],
    resolved: ["artifact.skill", "capability.cli", "foundation.a"],
    edges: [[1, 2]],
    masks: [1, 2, 16],
    requires: { "capability.cli": ["foundation.a"] },
  });
  assert.doesNotThrow(() => playground.validateProjection(required));

  const defaulted = singleCaseProjection({
    defaults: ["lifecycle.composition-state"],
    resolved: ["artifact.skill", "lifecycle.composition-state", "foundation.a"],
    edges: [[1, 2]],
    masks: [1, 4, 16],
    requires: { "lifecycle.composition-state": ["foundation.a"] },
  });
  assert.doesNotThrow(() => playground.validateProjection(defaulted));
});

test("dependency chain reachable from an explicit optional include is accepted", () => {
  const value = clone(fixture);
  const recipe = value.recipes[0];
  recipe.required_components = [];
  recipe.default_components = [];
  recipe.optional_components = ["capability.cli"];
  recipe.case_count = 2;
  recipe.cases = [
    { valid: true, error: null, outcome_id: 0, selection_reason_masks: [1] },
    { valid: true, error: null, outcome_id: 1, selection_reason_masks: [1, 8, 16] },
  ];
  for (const component of value.components) component.requires = [];
  upsertComponent(value, "foundation.a", []);
  upsertComponent(value, "capability.cli", ["foundation.a"]);
  value.outcomes = [
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
      resolved_components: ["artifact.skill", "capability.cli", "foundation.a"],
      dependency_edges: [[1, 2]],
      contract_ids: [],
      material_ids: [],
      initial_plan: { action_counts: { create: 0 }, conflict_count: 0 },
    },
  ];
  assert.doesNotThrow(() => playground.validateProjection(value));
});
