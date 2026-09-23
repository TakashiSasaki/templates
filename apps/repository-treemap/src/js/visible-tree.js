export function maxDescendantDepth(directory) {
  if (!directory.children.length) return 0;
  return 1 + Math.max(...directory.children.map(maxDescendantDepth));
}

export function projectDirectoryToDepth(directory, maxRelativeDepth) {
  const limit = maxRelativeDepth === Infinity
    ? Infinity
    : Math.max(0, Math.floor(maxRelativeDepth));

  const project = (source, depth) => ({
    source,
    name: source.name,
    path: source.path,
    fileCount: source.fileCount,
    totalSize: source.totalSize,
    hasChildren: source.children.length > 0,
    children: depth < limit
      ? source.children.map((child) => project(child, depth + 1))
      : []
  });

  return project(directory, 0);
}
