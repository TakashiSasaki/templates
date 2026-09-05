import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");

function fixture() {
  return JSON.parse(readFileSync(new URL("./fixtures/composition-playground-v1.json", import.meta.url), "utf8"));
}

test("the .git segment restriction remains material-destination-specific", () => {
  const value = fixture();
  value.recipes[0].source_path = ".git/recipes/skill.json";
  value.components[0].source_path = ".git/components/artifact.skill.json";
  assert.doesNotThrow(
    () => playground.validateProjection(value),
    "Composition relative-path source metadata must not inherit the Site material-destination guard",
  );
});
