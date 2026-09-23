import test from "node:test";
import assert from "node:assert/strict";
import { maxDescendantDepth, projectDirectoryToDepth } from "../src/js/visible-tree.js";

const leaf = { name: "leaf", path: "a/b/leaf", fileCount: 1, totalSize: 10, children: [] };
const b = { name: "b", path: "a/b", fileCount: 2, totalSize: 20, children: [leaf] };
const a = { name: "a", path: "a", fileCount: 3, totalSize: 30, children: [b] };
const root = { name: "site", path: "", fileCount: 4, totalSize: 40, children: [a] };

test("maxDescendantDepth measures from the current focus", () => {
  assert.equal(maxDescendantDepth(root), 3);
  assert.equal(maxDescendantDepth(a), 2);
  assert.equal(maxDescendantDepth(leaf), 0);
});

test("projectDirectoryToDepth collapses deeper descendants but keeps aggregate source metrics", () => {
  const projected = projectDirectoryToDepth(root, 1);
  assert.equal(projected.children.length, 1);
  assert.equal(projected.children[0].children.length, 0);
  assert.equal(projected.children[0].hasChildren, true);
  assert.equal(projected.children[0].source, a);
  assert.equal(projected.children[0].fileCount, 3);
  assert.equal(projected.children[0].totalSize, 30);
});

test("projectDirectoryToDepth supports all levels", () => {
  const projected = projectDirectoryToDepth(root, Infinity);
  assert.equal(projected.children[0].children[0].children[0].name, "leaf");
});
