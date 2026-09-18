import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function buildV4Provenance() {
  return {
    schema_version: 3,
    repository: "TakashiSasaki/templates",
    site_commit: "c".repeat(40),
    integration: {
      schema_version: 4,
      producer: { authority: "integration", revision: "e".repeat(40) },
      identity: "f".repeat(64),
      content_digest: "a".repeat(64),
      providers: {
        modeling: "a".repeat(40),
        composition: "b".repeat(40),
        policy: "d".repeat(40),
      },
    },
  };
}

test("Composition Playground accepts the exact v4 three-provider provenance projection", () => {
  const result = playground.validateBuildProvenance(buildV4Provenance());
  assert.equal(result.providerRevision, "b".repeat(40));
  assert.equal(result.policyRevision, "d".repeat(40));
  assert.deepEqual(result.providerRevisions, {
    modeling: "a".repeat(40),
    composition: "b".repeat(40),
    policy: "d".repeat(40),
  });
});

test("Composition Playground rejects a v4 provenance projection without Modeling", () => {
  const value = buildV4Provenance();
  delete value.integration.providers.modeling;
  assert.throws(
    () => playground.validateBuildProvenance(value),
    (error) => error.code === "MALFORMED_PROVENANCE"
  );
});

test("Composition Playground validates every v4 provider revision", () => {
  const invalids = [
    ["malformed Modeling", (value) => { value.integration.providers.modeling = "short"; }],
    ["malformed Composition", (value) => { value.integration.providers.composition = "B".repeat(40); }],
    ["malformed Policy", (value) => { value.integration.providers.policy = "D".repeat(40); }],
    ["extra provider", (value) => { value.integration.providers.other = "e".repeat(40); }],
    ["missing provider", (value) => { delete value.integration.providers.policy; }],
  ];
  for (const [label, mutate] of invalids) {
    const value = buildV4Provenance();
    mutate(value);
    assert.throws(
      () => playground.validateBuildProvenance(value),
      (error) => error.code === "MALFORMED_PROVENANCE",
      label,
    );
  }
});
