import { formatBytes, metricValue } from "./metrics.js";
import { projectDirectoryToDepth } from "./visible-tree.js";
import { cellLabelPresentation } from "./label-layout.js";
import { bindTouchLongPress } from "./touch-long-press.js";
import { assignReadableHierarchyValues, TREEMAP_SQUARIFY_RATIO } from "./layout-weights.js";

const COLORS = ["#315f8c", "#3f7652", "#8a6431", "#6d4c8a", "#8a3d4e", "#3f6e77"];
const HEADER_HEIGHT = 26;

function hierarchyFromDirectory(d3, directory, metricName, relativeDepth) {
  const projected = projectDirectoryToDepth(directory, relativeDepth);
  const hierarchy = d3.hierarchy(projected, (node) => node.children);
  assignReadableHierarchyValues(hierarchy, (data) => metricValue(data.source, metricName));
  return hierarchy.sort((a, b) => b.value - a.value);
}

function positionElement(element, node, inset = 0) {
  element.style.left = `${node.x0 + inset}px`;
  element.style.top = `${node.y0 + inset}px`;
  element.style.width = `${Math.max(0, node.x1 - node.x0 - inset * 2)}px`;
  element.style.height = `${Math.max(0, node.y1 - node.y0 - inset * 2)}px`;
}

function colorForNode(node, topColor) {
  const top = node.ancestors().find((ancestor) => ancestor.depth === 1);
  return topColor.get(top?.data.path) ?? COLORS[0];
}

function appendCellLabel(cell, source, width, height) {
  const presentation = cellLabelPresentation(width, height);
  const label = document.createElement("span");
  label.className = `node-label node-label--${presentation.density}`;
  label.style.setProperty("--node-label-font-size", `${presentation.fontSize}px`);
  const name = document.createElement("span");
  name.className = "node-name";
  name.textContent = source.name;
  label.append(name);
  if (presentation.showMeta) {
    const meta = document.createElement("span");
    meta.className = "node-meta";
    meta.textContent = `${source.fileCount} files · ${formatBytes(source.totalSize)}`;
    label.append(meta);
  }
  cell.append(label);
}

export function renderTreemap({ d3, container, directory, metricName, relativeDepth, onZoom, onDetails = () => {} }) {
  container.replaceChildren();
  const width = Math.max(container.clientWidth, 320);
  const height = Math.max(container.clientHeight, 420);
  const hierarchy = hierarchyFromDirectory(d3, directory, metricName, relativeDepth);

  d3.treemap()
    .tile(d3.treemapSquarify.ratio(TREEMAP_SQUARIFY_RATIO))
    .size([width, height])
    .paddingOuter(2)
    .paddingTop((node) => node.depth > 0 && node.children ? HEADER_HEIGHT : 2)
    .paddingInner(1)
    .round(true)(hierarchy);

  const topColor = new Map();
  hierarchy.children?.forEach((node, index) => topColor.set(node.data.path, COLORS[index % COLORS.length]));
  const nodes = hierarchy.descendants().filter((candidate) => candidate.depth > 0);

  for (const node of nodes) {
    const source = node.data.source;
    const hasVisibleChildren = Boolean(node.children?.length);
    const zoomable = source.children.length > 0;
    const color = colorForNode(node, topColor);

    if (hasVisibleChildren) {
      const frame = document.createElement("div");
      frame.className = "node node-parent-frame";
      frame.style.background = color;
      frame.style.zIndex = String(node.depth * 2);
      positionElement(frame, node);
      container.append(frame);
      continue;
    }

    const cell = document.createElement(zoomable ? "button" : "div");
    if (cell instanceof HTMLButtonElement) cell.type = "button";
    cell.className = "node node-cell";
    cell.style.background = color;
    cell.style.zIndex = String(node.depth * 2);
    cell.dataset.zoomable = String(zoomable);
    positionElement(cell, node);

    const cellWidth = Math.max(0, node.x1 - node.x0);
    const cellHeight = Math.max(0, node.y1 - node.y0);
    appendCellLabel(cell, source, cellWidth, cellHeight);
    cell.title = `${source.path || "/"}\n${source.fileCount} files\n${formatBytes(source.totalSize)}`;
    bindTouchLongPress(cell, () => onDetails(source));
    if (zoomable) cell.addEventListener("click", () => onZoom(source));
    container.append(cell);
  }

  for (const node of nodes.filter((candidate) => candidate.children?.length)) {
    const source = node.data.source;
    const header = document.createElement("button");
    header.type = "button";
    header.className = "node-header";
    header.style.left = `${node.x0 + 3}px`;
    header.style.top = `${node.y0 + 3}px`;
    header.style.width = `${Math.max(0, node.x1 - node.x0 - 6)}px`;
    header.style.height = `${Math.max(0, Math.min(HEADER_HEIGHT - 5, node.y1 - node.y0 - 6))}px`;
    header.style.zIndex = String(node.depth * 2 + 1);
    header.style.background = colorForNode(node, topColor);
    header.textContent = source.name;
    header.title = `${source.path || "/"}\n${source.fileCount} files\n${formatBytes(source.totalSize)}`;
    bindTouchLongPress(header, () => onDetails(source));
    header.addEventListener("click", () => onZoom(source));
    container.append(header);
  }
}
