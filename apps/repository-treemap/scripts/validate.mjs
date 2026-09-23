import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const required = [
  "src/index.html",
  "src/css/app.css",
  "src/js/main.js",
  "src/js/github-api.js",
  "src/js/repository-tree.js",
  "src/js/metrics.js",
  "src/js/treemap-view.js",
  "src/config/defaults.json"
];

await Promise.all(required.map((relativePath) => access(path.join(root, relativePath))));
const index = await readFile(path.join(root, "src/index.html"), "utf8");
if (!index.includes('type="module" src="./js/main.js"')) throw new Error("index.html must load main.js as an ES module");

const main = await readFile(path.join(root, "src/js/main.js"), "utf8");
if (!main.includes("https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm")) throw new Error("D3 dependency must remain exact-version pinned");

const defaults = JSON.parse(await readFile(path.join(root, "src/config/defaults.json"), "utf8"));
if (!Array.isArray(defaults.branches) || defaults.branches.length === 0) throw new Error("defaults.branches must be a non-empty array");
console.log("Validation passed");
