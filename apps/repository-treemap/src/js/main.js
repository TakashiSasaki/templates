import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { fetchBranchTree } from "./github-api.js";
import { buildDirectoryTree } from "./repository-tree.js";
import { formatBytes } from "./metrics.js";
import { maxDescendantDepth } from "./visible-tree.js";
import { renderTreemap } from "./treemap-view.js";
import { registerRepositoryTreemapServiceWorker, requestGitHubPrefetch } from "./service-worker-client.js";

const controls = {
  branch: document.querySelector("#branch-select"),
  depth: document.querySelector("#depth-select"),
  up: document.querySelector("#up-button"),
  root: document.querySelector("#root-button"),
  metric: [...document.querySelectorAll('input[name="metric"]')]
};
const status = document.querySelector("#status");
const breadcrumb = document.querySelector("#breadcrumb");
const details = document.querySelector("#details");
const treemap = document.querySelector("#treemap");
const state = { config: null, metric: "fileCount", relativeDepth: 2, branch: null, trees: new Map(), path: [] };

function setStatus(message, kind = "info") { status.textContent = message; status.dataset.kind = kind; }
function focusDirectory() { return state.path.at(-1); }
function effectiveDepth(focus) {
  const maximum = maxDescendantDepth(focus);
  return state.relativeDepth === Infinity ? Infinity : Math.min(state.relativeDepth, maximum);
}
function refreshDepthControl(focus) {
  const maximum = maxDescendantDepth(focus);
  controls.depth.replaceChildren();
  if (maximum === 0) { controls.depth.add(new Option("0", "0")); controls.depth.disabled = true; return; }
  controls.depth.disabled = false;
  for (let depth = 1; depth <= maximum; depth += 1) controls.depth.add(new Option(String(depth), String(depth)));
  controls.depth.add(new Option("All", "all"));
  if (state.relativeDepth !== Infinity) state.relativeDepth = Math.min(Math.max(1, state.relativeDepth), maximum);
  controls.depth.value = state.relativeDepth === Infinity ? "all" : String(state.relativeDepth);
}
function render() {
  const focus = focusDirectory();
  if (!focus) return;
  refreshDepthControl(focus);
  const depth = effectiveDepth(focus);
  breadcrumb.textContent = [state.branch, ...state.path.slice(1).map((item) => item.name)].join(" › ");
  controls.up.disabled = state.path.length <= 1;
  controls.root.disabled = state.path.length <= 1;
  const depthLabel = depth === Infinity ? "all levels" : `${depth} relative level${depth === 1 ? "" : "s"}`;
  details.textContent = `${focus.fileCount.toLocaleString()} files · ${formatBytes(focus.totalSize)} · showing ${depthLabel}`;
  renderTreemap({ d3, container: treemap, directory: focus, metricName: state.metric, relativeDepth: depth, onZoom(directory) { state.path.push(directory); render(); } });
}
async function selectBranch(branch) {
  state.branch = branch;
  controls.branch.value = branch;
  setStatus(`Loading ${branch}…`);
  try {
    if (!state.trees.has(branch)) {
      const entries = await fetchBranchTree(state.config.owner, state.config.repository, branch);
      state.trees.set(branch, buildDirectoryTree(branch, entries));
    }
    state.path = [state.trees.get(branch)];
    setStatus(`Loaded ${state.config.owner}/${state.config.repository}@${branch}`);
    render();
  } catch (error) { setStatus(error.message, "error"); treemap.replaceChildren(); }
}
async function start() {
  const response = await fetch("./config/defaults.json");
  if (!response.ok) throw new Error("Unable to load defaults.json");
  state.config = await response.json();
  state.metric = state.config.defaultMetric;
  state.relativeDepth = state.config.defaultRelativeDepth;
  for (const branch of state.config.branches) controls.branch.add(new Option(branch, branch));
  controls.metric.find((input) => input.value === state.metric).checked = true;
  registerRepositoryTreemapServiceWorker().then((registration) => requestGitHubPrefetch(registration, state.config));
  await selectBranch(state.config.branches[0]);
}
controls.branch.addEventListener("change", () => selectBranch(controls.branch.value));
controls.depth.addEventListener("change", () => { state.relativeDepth = controls.depth.value === "all" ? Infinity : Number.parseInt(controls.depth.value, 10); render(); });
controls.metric.forEach((input) => input.addEventListener("change", () => { state.metric = input.value; render(); }));
controls.up.addEventListener("click", () => { if (state.path.length > 1) state.path.pop(); render(); });
controls.root.addEventListener("click", () => { state.path = [state.trees.get(state.branch)]; render(); });
window.addEventListener("resize", () => render());
start().catch((error) => setStatus(error.message, "error"));
