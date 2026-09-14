#!/usr/bin/env node
/** Validate the exact Composition candidate projection with Site-owned consumer logic. */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { createRequire } from "node:module";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const consumer = require("../assets/javascripts/composition-playground.js");
const compositionRoot = process.argv[2];
if (!compositionRoot) throw new Error("usage: check_composition_playground_candidate_projection.mjs COMPOSITION_ROOT");

const root = resolve(compositionRoot);
const manifest = JSON.parse(
  await readFile(resolve(root, "generated/composition-playground-publication.json"), "utf8"),
);
const projection = JSON.parse(
  gunzipSync(await readFile(resolve(root, "generated/composition-playground-v1.json.gz"))),
);
const validated = consumer.validateProjection(projection);

assert.match(manifest.semantic_revision, /^[0-9a-f]{40}$/);
assert.equal(validated.semanticRevision, manifest.semantic_revision);
assert.ok(
  projection.outcomes.some((outcome) =>
    outcome.resolved_components.includes("topology.hub-and-orphan") &&
    outcome.resolved_components.includes("workspace.bare-worktree")
  ),
  "candidate projection must preserve Hub-and-Orphan x Bare Worktree coexistence",
);
console.log(
  `Site candidate projection compatibility passed: semantic=${validated.semanticRevision} outcomes=${validated.outcomeById.size}`,
);
