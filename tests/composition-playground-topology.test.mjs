import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
const require = createRequire(import.meta.url);
const playground = require("../assets/javascripts/composition-playground.js");
async function topologyFixture() {
  const text = await readFile(new URL("./fixtures/composition-playground-v1.json", import.meta.url), "utf8");
  const raw = JSON.parse(text.replaceAll("capability.cli", "topology.hub-and-orphan"));
  raw.components.find(c => c.id === "topology.hub-and-orphan").role = "topology";
  return raw;
}
async function workspaceFixture() {
  const text = await readFile(new URL("./fixtures/composition-playground-v1.json", import.meta.url), "utf8");
  const raw = JSON.parse(text.replaceAll("capability.cli", "workspace.bare-worktree"));
  raw.components.find(c => c.id === "workspace.bare-worktree").role = "workspace";
  return raw;
}
test("topology remains an optional independent axis in a valid provider projection", async () => {
  const raw = await topologyFixture();
  assert.doesNotThrow(() => playground.validateProjection(raw));
});
test("strict consumer rejects multiple topology selections", async () => {
  const raw = await topologyFixture();
  raw.outcomes[0].resolved_components.push("topology.first", "topology.second");
  assert.throws(() => playground.validateProjection(raw), /at most one repository topology/);
});
test("workspace remains an optional independent axis in a valid provider projection", async () => {
  const raw = await workspaceFixture();
  assert.doesNotThrow(() => playground.validateProjection(raw));
});
test("strict consumer rejects multiple workspace selections", async () => {
  const raw = await workspaceFixture();
  raw.outcomes[0].resolved_components.push("workspace.first", "workspace.second");
  assert.throws(() => playground.validateProjection(raw), /at most one workspace topology/);
});
