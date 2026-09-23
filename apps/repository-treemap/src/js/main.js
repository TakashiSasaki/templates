import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { fetchBranchTree } from "./github-api.js";
import { buildDirectoryTree } from "./repository-tree.js";
import { formatBytes } from "./metrics.js";
import { renderTreemap } from "./treemap-view.js";

const controls = {
  branch: document.querySelector("#branch-select"),
  up: document.querySelector("#up-button"),
  root: document.querySelector("#root-button"),
  metric: [...document.querySelectorAll('input[name="metric"]')]
};
const status = document.querySelector("#status");
const breadcrumb = document.querySelector("#breadcrumb");
const details = document.querySelector("#details");
const treemap = document.querySelector("#treemap");

const state = { config: null, metric: "fileCount", branch: null, trees: new Map(), path: [] };

function setStatus(message, kind = "info") {
  status.textContent = message;
  status.dataset.kind = kind;
}

function focusDirectory() {
  return state.path.at(-1);
}

function render() {
  const focus = focusDirectory();
  if (!focus) return;
  breadcrumb.textContent = [state.branch, ...state.path.slice(1).map((item) => item.name)].join(" › ");
  controls.up.disabled = state.path.length <= 1;
  controls.root.disabled = state.path.length <= 1;
  details.textContent = `${focus.fileCount.toLocaleString()} files · ${formatBytes(focus.totalSize)}`;
  renderTreemap({
    d3,
    container: treemap,
    directory: focus,
    metricName: state.metric,
    onZoom(directory) {
      state.path.push(directory);
      render();
    }
  });
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
  } catch (error) {
    setStatus(error.message, "error");
    treemap.replaceChildren();
  }
}

async function start() {
  const response = await fetch("./config/defaults.json");
  if (!response.ok) throw new Error("Unable to load defaults.json");
  state.config = await response.json();
  state.metric = state.config.defaultMetric;

  for (const branch of state.config.branches) {
    controls.branch.add(new Option(branch, branch));
  }
  controls.metric.find((input) => input.value === state.metric).checked = true;
  await selectBranch(state.config.branches[0]);
}

controls.branch.addEventListener("change", () => selectBranch(controls.branch.value));
controls.metric.forEach((input) => input.addEventListener("change", () => {
  state.metric = input.value;
  render();
}));
controls.up.addEventListener("click", () => {
  if (state.path.length > 1) state.path.pop();
  render();
});
controls.root.addEventListener("click", () => {
  state.path = [state.trees.get(state.branch)];
  render();
});
window.addEventListener("resize", () => render());

start().catch((error) => setStatus(error.message, "error"));
