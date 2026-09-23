import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { fetchBranchTree } from "./github-api.js";
import { buildDirectoryTree } from "./repository-tree.js";
import { formatBytes } from "./metrics.js";
import { maxDescendantDepth } from "./visible-tree.js";
import { renderTreemap } from "./treemap-view.js";
import { registerRepositoryTreemapServiceWorker, requestGitHubPrefetch } from "./service-worker-client.js";
import { isCacheTimestampFresh } from "./cache-policy.js";
import { isPointOutsideRect } from "./dialog-dismiss.js";

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
const nodeDetails = {
  dialog: document.querySelector("#node-details-dialog"),
  title: document.querySelector("#node-details-title"),
  path: document.querySelector("#node-details-path"),
  files: document.querySelector("#node-details-files"),
  size: document.querySelector("#node-details-size"),
  children: document.querySelector("#node-details-children"),
  close: document.querySelector("#node-details-close"),
  zoom: document.querySelector("#node-details-zoom")
};
const state = { config: null, metric: "fileCount", relativeDepth: 2, branch: null, trees: new Map(), path: [] };
let detailedDirectory = null;

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
function showDirectoryDetails(directory) {
  detailedDirectory = directory;
  nodeDetails.title.textContent = directory.name;
  nodeDetails.path.textContent = directory.path ? `${state.branch}/${directory.path}` : state.branch;
  nodeDetails.files.textContent = directory.fileCount.toLocaleString();
  nodeDetails.size.textContent = formatBytes(directory.totalSize);
  nodeDetails.children.textContent = directory.children.length.toLocaleString();
  nodeDetails.zoom.hidden = directory.children.length === 0;
  if (!nodeDetails.dialog.open) nodeDetails.dialog.showModal();
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
  renderTreemap({
    d3, container: treemap, directory: focus, metricName: state.metric, relativeDepth: depth,
    onZoom(directory) { state.path.push(directory); render(); },
    onDetails: showDirectoryDetails
  });
}
async function selectBranch(branch) {
  state.branch = branch;
  controls.branch.value = branch;
  setStatus(`Loading ${branch}…`);
  try {
    const cached = state.trees.get(branch);
    if (!cached || !isCacheTimestampFresh(cached.fetchedAt)) {
      const entries = await fetchBranchTree(state.config.owner, state.config.repository, branch);
      state.trees.set(branch, { tree: buildDirectoryTree(branch, entries), fetchedAt: Date.now() });
    }
    state.path = [state.trees.get(branch).tree];
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

nodeDetails.close.addEventListener("click", () => nodeDetails.dialog.close());
nodeDetails.zoom.addEventListener("click", () => {
  if (!detailedDirectory?.children.length) return;
  const target = detailedDirectory;
  nodeDetails.dialog.close();
  state.path.push(target);
  render();
});
nodeDetails.dialog.addEventListener("click", (event) => {
  const rect = nodeDetails.dialog.getBoundingClientRect();
  if (isPointOutsideRect(event.clientX, event.clientY, rect)) nodeDetails.dialog.close();
});
nodeDetails.dialog.addEventListener("close", () => { detailedDirectory = null; });
controls.branch.addEventListener("change", () => selectBranch(controls.branch.value));
controls.depth.addEventListener("change", () => { state.relativeDepth = controls.depth.value === "all" ? Infinity : Number.parseInt(controls.depth.value, 10); render(); });
controls.metric.forEach((input) => input.addEventListener("change", () => { state.metric = input.value; render(); }));
controls.up.addEventListener("click", () => { if (state.path.length > 1) state.path.pop(); render(); });
controls.root.addEventListener("click", () => { state.path = [state.trees.get(state.branch).tree]; render(); });
window.addEventListener("resize", () => render());
start().catch((error) => setStatus(error.message, "error"));
