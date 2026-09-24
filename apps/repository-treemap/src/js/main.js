import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { fetchBranchTree } from "./github-api.js";
import { buildDirectoryTree } from "./repository-tree.js";
import { formatBytes } from "./metrics.js";
import { maxDescendantDepth } from "./visible-tree.js";
import { renderTreemap } from "./treemap-view.js";
import { registerRepositoryTreemapServiceWorker, requestGitHubPrefetch } from "./service-worker-client.js";
import { isCacheTimestampFresh } from "./cache-policy.js";
import { isPointOutsideRect } from "./dialog-dismiss.js";
import {
  currentFullscreenElement,
  exitNativeFullscreen,
  fullscreenButtonLabel,
  requestNativeFullscreen,
  supportsNativeFullscreen
} from "./fullscreen.js";
import {
  loadPreferences,
  relativeDepthForBranch,
  savePreferences,
  withBranchRelativeDepth,
  withLastBranch
} from "./preferences.js";

const appShell = document.querySelector("#app-shell");
const viewTabList = document.querySelector("#view-tabs");
const branchTabs = document.querySelector("#branch-tabs");
const controls = {
  depth: document.querySelector("#depth-select"),
  up: document.querySelector("#up-button"),
  root: document.querySelector("#root-button"),
  fullscreen: document.querySelector("#fullscreen-button"),
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
const state = {
  config: null,
  metric: "fileCount",
  relativeDepth: 2,
  branch: null,
  trees: new Map(),
  path: [],
  preferences: { lastBranch: null, relativeDepthByBranch: {} }
};
let detailedDirectory = null;
let fallbackFullscreen = false;
let preferenceStorage = null;

try {
  preferenceStorage = window.localStorage;
} catch {
  preferenceStorage = null;
}

function setStatus(message, kind = "info") { status.textContent = message; status.dataset.kind = kind; }
function focusDirectory() { return state.path.at(-1); }

function viewTabButtons() {
  return [...viewTabList.querySelectorAll('[role="tab"]')];
}

function selectView(view) {
  for (const tab of viewTabButtons()) {
    const selected = tab.dataset.view === view;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    const panel = document.querySelector(`#${tab.getAttribute("aria-controls")}`);
    if (panel) panel.hidden = !selected;
  }
  if (view === "treemap") requestAnimationFrame(() => render());
}

function branchTabButtons() {
  return [...branchTabs.querySelectorAll('[role="tab"]')];
}

function updateBranchTabs(selectedBranch) {
  let selectedTab = null;
  for (const tab of branchTabButtons()) {
    const selected = tab.dataset.branch === selectedBranch;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected) selectedTab = tab;
  }
  selectedTab?.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function initializeBranchTabs(branches) {
  branchTabs.replaceChildren();
  for (const branch of branches) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "branch-tab";
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", "false");
    tab.tabIndex = -1;
    tab.dataset.branch = branch;
    tab.textContent = branch;
    tab.addEventListener("click", () => selectBranch(branch));
    branchTabs.append(tab);
  }
}

function effectiveDepth(focus) {
  const maximum = maxDescendantDepth(focus);
  return state.relativeDepth === Infinity ? Infinity : Math.min(state.relativeDepth, maximum);
}

function refreshDepthControl(focus) {
  const maximum = maxDescendantDepth(focus);
  controls.depth.replaceChildren();
  if (maximum === 0) {
    controls.depth.add(new Option("0", "0"));
    controls.depth.disabled = true;
    return;
  }
  controls.depth.disabled = false;
  for (let depth = 1; depth <= maximum; depth += 1) controls.depth.add(new Option(String(depth), String(depth)));
  controls.depth.add(new Option("All", "all"));
  controls.depth.value = state.relativeDepth === Infinity
    ? "all"
    : String(Math.min(Math.max(1, state.relativeDepth), maximum));
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
  if (!focus || document.querySelector("#view-panel-treemap")?.hidden) return;
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
  state.relativeDepth = relativeDepthForBranch(state.preferences, branch, state.config.defaultRelativeDepth);
  state.preferences = withLastBranch(state.preferences, branch);
  savePreferences(preferenceStorage, state.preferences);
  updateBranchTabs(branch);
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
  } catch (error) {
    setStatus(error.message, "error");
    treemap.replaceChildren();
  }
}

function fullscreenActive() {
  return Boolean(currentFullscreenElement(document)) || fallbackFullscreen;
}

function syncFullscreenUi() {
  const active = fullscreenActive();
  controls.fullscreen.textContent = fullscreenButtonLabel(active);
  controls.fullscreen.setAttribute("aria-pressed", String(active));
}

function setFallbackFullscreen(active) {
  fallbackFullscreen = active;
  appShell.classList.toggle("is-fallback-fullscreen", active);
  document.body.classList.toggle("app-fallback-fullscreen", active);
  syncFullscreenUi();
  requestAnimationFrame(() => render());
}

async function toggleFullscreen() {
  if (currentFullscreenElement(document)) {
    await exitNativeFullscreen(document);
    return;
  }
  if (fallbackFullscreen) {
    setFallbackFullscreen(false);
    return;
  }
  if (supportsNativeFullscreen(appShell, document)) {
    try {
      if (await requestNativeFullscreen(appShell)) {
        syncFullscreenUi();
        return;
      }
    } catch (error) {
      console.warn("Native fullscreen failed; using app fullscreen fallback", error);
    }
  }
  setFallbackFullscreen(true);
}

async function start() {
  const response = await fetch("./config/defaults.json");
  if (!response.ok) throw new Error("Unable to load defaults.json");
  state.config = await response.json();
  state.metric = state.config.defaultMetric;
  state.preferences = loadPreferences(preferenceStorage, state.config.branches);
  initializeBranchTabs(state.config.branches);
  controls.metric.find((input) => input.value === state.metric).checked = true;
  registerRepositoryTreemapServiceWorker().then((registration) => requestGitHubPrefetch(registration, state.config));
  const initialBranch = state.preferences.lastBranch ?? state.config.branches[0];
  await selectBranch(initialBranch);
  syncFullscreenUi();
}

viewTabList.addEventListener("click", (event) => {
  const tab = event.target.closest('[role="tab"][data-view]');
  if (tab) selectView(tab.dataset.view);
});

viewTabList.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const tabs = viewTabButtons();
  const currentIndex = tabs.indexOf(document.activeElement);
  if (currentIndex < 0) return;
  event.preventDefault();
  let nextIndex = currentIndex;
  if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = tabs.length - 1;
  const next = tabs[nextIndex];
  next.focus();
  selectView(next.dataset.view);
});

branchTabs.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const tabs = branchTabButtons();
  const currentIndex = tabs.indexOf(document.activeElement);
  if (currentIndex < 0) return;
  event.preventDefault();
  let nextIndex = currentIndex;
  if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = tabs.length - 1;
  const next = tabs[nextIndex];
  next.focus();
  selectBranch(next.dataset.branch);
});

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

controls.fullscreen.addEventListener("click", () => {
  toggleFullscreen().catch((error) => {
    console.warn("Fullscreen toggle failed", error);
    setFallbackFullscreen(!fallbackFullscreen);
  });
});
for (const eventName of ["fullscreenchange", "webkitfullscreenchange"]) {
  document.addEventListener(eventName, () => {
    if (currentFullscreenElement(document)) fallbackFullscreen = false;
    syncFullscreenUi();
    requestAnimationFrame(() => render());
  });
}

controls.depth.addEventListener("change", () => {
  state.relativeDepth = controls.depth.value === "all" ? Infinity : Number.parseInt(controls.depth.value, 10);
  state.preferences = withBranchRelativeDepth(state.preferences, state.branch, state.relativeDepth);
  savePreferences(preferenceStorage, state.preferences);
  render();
});
controls.metric.forEach((input) => input.addEventListener("change", () => { state.metric = input.value; render(); }));
controls.up.addEventListener("click", () => { if (state.path.length > 1) state.path.pop(); render(); });
controls.root.addEventListener("click", () => { state.path = [state.trees.get(state.branch).tree]; render(); });
window.addEventListener("resize", () => render());
start().catch((error) => setStatus(error.message, "error"));
