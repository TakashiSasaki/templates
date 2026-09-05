import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function projectionWithTwoMaterialOwners() {
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
      required_components: ["capability.cli"],
      default_components: [],
      optional_components: [],
      case_count: 1,
      source_path: "recipes/skill.json",
      cases: [{
        valid: true,
        error: null,
        outcome_id: 0,
        selection_reason_masks: [1, 2],
      }],
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
        material_declarations: [{ destination: "SKILL.md" }],
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
        material_declarations: [{ destination: "bin/tool.sh" }],
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
    outcomes: [{
      index: 0,
      resolved_components: ["artifact.skill", "capability.cli"],
      dependency_edges: [],
      contract_ids: [],
      material_ids: [0, 1],
      initial_plan: { action_counts: { create: 2 }, conflict_count: 0 },
    }],
  };
}

function assertMalformed(value, message) {
  assert.throws(
    () => playground.validateProjection(value),
    (error) => error.code === "MALFORMED_PROJECTION",
    message,
  );
}

test("material projection completeness binds each destination to its resolved owner", () => {
  const valid = projectionWithTwoMaterialOwners();
  assert.doesNotThrow(() => playground.validateProjection(valid));

  const swapped = structuredClone(valid);
  swapped.materials[0].component = "capability.cli";
  swapped.materials[1].component = "artifact.skill";
  assertMalformed(
    swapped,
    "swapping resolved material owners while keeping destinations unchanged must fail",
  );
});

test("published variants for the same owner and destination remain interchangeable", () => {
  const value = projectionWithTwoMaterialOwners();
  value.materials.push({
    index: 2,
    component: "capability.cli",
    destination: "bin/tool.sh",
    ownership: "generated",
    sha256: "3".repeat(64),
  });
  value.outcomes[0].material_ids = [0, 2];
  assert.doesNotThrow(() => playground.validateProjection(value));
});
