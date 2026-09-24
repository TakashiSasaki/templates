import test from "node:test";
import assert from "node:assert/strict";
import { CLOSE_FALLBACK_DELAY_MS, closeFallbackAction } from "../src/js/app-close.js";

test("close fallback delay is short enough to feel immediate", () => {
  assert.equal(CLOSE_FALLBACK_DELAY_MS, 120);
});

test("close falls back to browser history when a previous entry exists", () => {
  assert.equal(closeFallbackAction(2), "back");
  assert.equal(closeFallbackAction(10), "back");
});

test("close falls back to a blank document when no previous entry exists", () => {
  assert.equal(closeFallbackAction(1), "blank");
  assert.equal(closeFallbackAction(0), "blank");
  assert.equal(closeFallbackAction(Number.NaN), "blank");
});
