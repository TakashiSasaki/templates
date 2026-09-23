export const METRICS = Object.freeze({
  fileCount: { label: "files", accessor: (node) => node.fileCount },
  totalSize: { label: "bytes", accessor: (node) => node.totalSize }
});

export function metricValue(node, metricName) {
  const metric = METRICS[metricName];
  if (!metric) throw new Error(`Unknown metric: ${metricName}`);
  return metric.accessor(node);
}

export function formatBytes(bytes) {
  const units = ["B", "KiB", "MiB", "GiB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  const digits = index === 0 || value >= 100 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(digits)} ${units[index]}`;
}
