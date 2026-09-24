import test from "node:test";
import assert from "node:assert/strict";
import {
  PREFERENCES_STORAGE_KEY,
  loadPreferences,
  relativeDepthForBranch,
  savePreferences,
  withBranchRelativeDepth,
  withLastBranch
} from "../src/js/preferences.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    snapshot() { return Object.fromEntries(values); }
  };
}

const branches = ["site", "integration", "composition", "policy", "modeling"];

test("preferences remember last branch and per-branch relative depths", () => {
  const storage = memoryStorage();
  let preferences = loadPreferences(storage, branches);
  preferences = withLastBranch(preferences, "policy");
  preferences = withBranchRelativeDepth(preferences, "site", 3);
  preferences = withBranchRelativeDepth(preferences, "policy", Infinity);
  assert.equal(savePreferences(storage, preferences), true);

  const restored = loadPreferences(storage, branches);
  assert.equal(restored.lastBranch, "policy");
  assert.equal(relativeDepthForBranch(restored, "site", 2), 3);
  assert.equal(relativeDepthForBranch(restored, "policy", 2), Infinity);
  assert.equal(relativeDepthForBranch(restored, "composition", 2), 2);
});

test("unknown branches and invalid depth values are ignored", () => {
  const storage = memoryStorage({
    [PREFERENCES_STORAGE_KEY]: JSON.stringify({
      lastBranch: "deleted-branch",
      relativeDepthByBranch: { site: 0, policy: 4, missing: 9 }
    })
  });
  const restored = loadPreferences(storage, branches);
  assert.equal(restored.lastBranch, null);
  assert.deepEqual(restored.relativeDepthByBranch, { policy: 4 });
});

test("malformed or unavailable storage fails open to defaults", () => {
  const malformed = memoryStorage({ [PREFERENCES_STORAGE_KEY]: "{" });
  assert.deepEqual(loadPreferences(malformed, branches), { lastBranch: null, relativeDepthByBranch: {} });
  assert.deepEqual(loadPreferences(null, branches), { lastBranch: null, relativeDepthByBranch: {} });
});
