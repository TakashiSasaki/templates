import { formatBytes, metricValue } from "./metrics.js";
import { projectDirectoryToDepth } from "./visible-tree.js";

const COLORS = ["#315f8c", "#3f7652", "#8a6431", "#6d4c8a", "#8a3d4e", "#3f6e77"];

function hierarchyFromDirectory(d3, directory, metricName, relativeDepth) {
  const projected = projectDirectoryToDepth(directory, relativeDepth);
  const hierarchy = d3.hierarchy(projected, (node) => node.children);
  hierarchy.each((node) => {
    node.value = metricValue(node.data.source, metricName);
  });
  return hierarchy.sort((a, b) => b.value - a.value);
}

export function renderTreemap({ d3, container, directory, metricName, relativeDepth, onZoom }) {
  container.replaceChildren();
  const width = Math.max(container.clientWidth, 320);
  const height = Math.max(container.clientHeight, 420);
  const hierarchy = hierarchyFromDirectory(d3, directory, metricName, relativeDepth);

  d3.treemap()
    .size([width, height])
    .paddingOuter(2)
    .paddingTop((node) => node.depth > 0 && node.children ? 20 : 2)
    .paddingInner(1)
    .round(true)(hierarchy);

  const topColor = new Map();
  hierarchy.children?.forEach((node, index) => topColor.set(node.data.path, COLORS[index % COLORS.length]));

  for (const node of hierarchy.descendants().filter((candidate) => candidate.depth > 0)) {
    const source = node.data.source;
    const zoomable = source.children.length > 0;
    const element = document.createElement(zoomable ? "button" : "div");
    if (element instanceof HTMLButtonElement) element.type = "button";
    element.className = "node";
    element.style.left = `${node.x0}px`;
    element.style.top = `${node.y0}px`;
    element.style.width = `${Math.max(0, node.x1 - node.x0)}px`;
    element.style.height = `${Math.max(0, node.y1 - node.y0)}px`;

    const top = node.ancestors().find((ancestor) => ancestor.depth === 1);
    element.style.background = topColor.get(top?.data.path) ?? COLORS[0];
    element.dataset.zoomable = String(zoomable);

    const area = (node.x1 - node.x0) * (node.y1 - node.y0);
    if (area > 2800) {
      const label = document.createElement("span");
      label.className = "node-label";
      label.innerHTML = `<span class="node-name"></span><span class="node-meta"></span>`;
      label.querySelector(".node-name").textContent = source.name;
      label.querySelector(".node-meta").textContent = `${source.fileCount} files · ${formatBytes(source.totalSize)}`;
      element.append(label);
    }

    element.title = `${source.path || "/"}\n${source.fileCount} files\n${formatBytes(source.totalSize)}`;
    if (zoomable) element.addEventListener("click", () => onZoom(source));
    container.append(element);
  }
}
