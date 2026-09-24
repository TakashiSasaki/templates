import test from "node:test";
import assert from "node:assert/strict";
import { cellLabelPresentation } from "../src/js/label-layout.js";

test("large cells use full labels with metadata", () => {
  assert.deepEqual(cellLabelPresentation(160, 80), { density: "full", showMeta: true, fontSize: 16 });
});

test("medium cells keep the directory name but drop metadata", () => {
  const result = cellLabelPresentation(70, 32);
  assert.equal(result.density, "compact");
  assert.equal(result.showMeta, false);
  assert.ok(result.fontSize >= 6);
});

test("small cells still request a tiny visible name label", () => {
  assert.deepEqual(cellLabelPresentation(18, 12), { density: "tiny", showMeta: false, fontSize: 6 });
});

test("invalid or zero geometry stays safe and still has a minimum font size", () => {
  assert.deepEqual(cellLabelPresentation(NaN, 0), { density: "tiny", showMeta: false, fontSize: 6 });
});
