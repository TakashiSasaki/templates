import { formatBytes, metricValue } from "./metrics.js";
import { projectDirectoryToDepth } from "./visible-tree.js";

const COLORS = ["#315f8c", "#3f7652", "#8a6431", "#6d4c8a", "#8a3d4e", "#3f6e77"];
const HEADER_HEIGHT = 26;

function hierarchyFromDirectory(d3, directory, metricName, relativeDepth) {
  const projected = projectDirectoryToDepth(directory, relativeDepth);
  const hierarchy = d3.hierarchy(projected, (node) => node.children);
  hierarchy.each((node) => { node.value = metricValue(node.data.source, metricName); });
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

export function renderTreemap({ d3, container, directory, metricName, relativeDepth, onZoom }) {
  container.replaceChildren();
  const width = Math.max(container.clientWidth, 320);
  const height = Math.max(container.clientHeight, 420);
  const hierarchy = hierarchyFromDirectory(d3, directory, metricName, relativeDepth);

  d3.treemap()
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

    const area = (node.x1 - node.x0) * (node.y1 - node.y0);
    if (area > 2800) {
      const label = document.createElement("span");
      label.className = "node-label";
      label.innerHTML = `<span class="node-name"></span><span class="node-meta"></span>`;
      label.querySelector(".node-name").textContent = source.name;
      label.querySelector(".node-meta").textContent = `${source.fileCount} files · ${formatBytes(source.totalSize)}`;
      cell.append(label);
    }

    cell.title = `${source.path || "/"}\n${source.fileCount} files\n${formatBytes(source.totalSize)}`;
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
    header.style.height = `${HEADER_HEIGHT - 5}px`;
    header.style.zIndex = String(node.depth * 2 + 1);
    header.style.background = colorForNode(node, topColor);
    header.textContent = source.name;
    header.title = `${source.path || "/"}\n${source.fileCount} files\n${formatBytes(source.totalSize)}`;
    header.addEventListener("click", () => onZoom(source));
    container.append(header);
  }
}
