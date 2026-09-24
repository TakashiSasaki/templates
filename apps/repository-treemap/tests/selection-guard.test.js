import test from "node:test";
import assert from "node:assert/strict";
import { createLatestSelectionGuard } from "../src/js/selection-guard.js";

test("only the latest branch-selection token remains current", () => {
  const guard = createLatestSelectionGuard();
  const first = guard.begin();
  assert.equal(guard.isCurrent(first), true);
  const second = guard.begin();
  assert.equal(guard.isCurrent(first), false);
  assert.equal(guard.isCurrent(second), true);
});
