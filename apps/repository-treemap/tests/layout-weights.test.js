import test from "node:test";
import assert from "node:assert/strict";
import {
  READABLE_WEIGHT_EXPONENT,
  MAX_MIN_SIBLING_SHARE,
  TREEMAP_SQUARIFY_RATIO,
  normalizedSiblingWeights,
  assignReadableHierarchyValues
} from "../src/js/layout-weights.js";

test("readable constants favor compact approximate layout", () => {
  assert.equal(READABLE_WEIGHT_EXPONENT, 0.8);
  assert.equal(MAX_MIN_SIBLING_SHARE, 0.02);
  assert.equal(TREEMAP_SQUARIFY_RATIO, 1.2);
});

test("one visible child receives the entire parent area", () => {
  assert.ok(Math.abs(normalizedSiblingWeights([3], 0.42)[0] - 0.42) < 1e-12);
});

test("weights fill the target and compress extreme ratios", () => {
  const weights = normalizedSiblingWeights([1, 1000], 1);
  assert.ok(Math.abs(weights.reduce((a, b) => a + b, 0) - 1) < 1e-12);
  assert.ok(weights[1] > weights[0]);
  assert.ok(weights[1] / weights[0] < 1000);
});

test("small siblings receive a soft minimum share", () => {
  const weights = normalizedSiblingWeights([1, 100000, 100000], 1);
  assert.ok(weights[0] >= 0.019);
});

test("each internal hierarchy node is exactly filled by visible children", () => {
  const leaf = (metric) => ({ data: { metric }, children: null, value: 0 });
  const a = { data: { metric: 100 }, children: [leaf(1), leaf(9)], value: 0 };
  const b = { data: { metric: 50 }, children: [leaf(5)], value: 0 };
  const root = { data: { metric: 150 }, children: [a, b], value: 0 };
  assignReadableHierarchyValues(root, (data) => data.metric);
  assert.ok(Math.abs(a.children.reduce((sum, child) => sum + child.value, 0) - a.value) < 1e-12);
  assert.ok(Math.abs(b.children.reduce((sum, child) => sum + child.value, 0) - b.value) < 1e-12);
  assert.ok(Math.abs(root.children.reduce((sum, child) => sum + child.value, 0) - root.value) < 1e-12);
});
