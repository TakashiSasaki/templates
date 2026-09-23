import test from "node:test";
import assert from "node:assert/strict";
import { buildDirectoryTree } from "../src/js/repository-tree.js";
import { metricValue, formatBytes } from "../src/js/metrics.js";

const entries = [
  { type: "blob", path: "src/main.js", size: 100 },
  { type: "blob", path: "src/lib/math.js", size: 50 },
  { type: "blob", path: "README.md", size: 25 },
  { type: "tree", path: "src", size: 0 }
];

test("buildDirectoryTree aggregates descendant files and bytes", () => {
  const root = buildDirectoryTree("site", entries);
  assert.equal(root.fileCount, 3);
  assert.equal(root.totalSize, 175);
  const src = root.children.find((node) => node.name === "src");
  assert.equal(src.fileCount, 2);
  assert.equal(src.totalSize, 150);
  const lib = src.children.find((node) => node.name === "lib");
  assert.equal(lib.fileCount, 1);
  assert.equal(lib.totalSize, 50);
});

test("metricValue switches between canonical metrics", () => {
  const node = { fileCount: 7, totalSize: 2048 };
  assert.equal(metricValue(node, "fileCount"), 7);
  assert.equal(metricValue(node, "totalSize"), 2048);
  assert.equal(formatBytes(2048), "2.00 KiB");
});
