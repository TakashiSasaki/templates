function newDirectory(name, path) {
  return { name, path, children: new Map(), fileCount: 0, totalSize: 0 };
}

export function buildDirectoryTree(branchName, gitTreeEntries) {
  const root = newDirectory(branchName, "");

  for (const entry of gitTreeEntries) {
    if (entry.type !== "blob") continue;
    const parts = entry.path.split("/");
    const size = Number.isFinite(entry.size) ? entry.size : 0;
    let directory = root;
    directory.fileCount += 1;
    directory.totalSize += size;

    for (let i = 0; i < parts.length - 1; i += 1) {
      const name = parts[i];
      const path = parts.slice(0, i + 1).join("/");
      if (!directory.children.has(name)) {
        directory.children.set(name, newDirectory(name, path));
      }
      directory = directory.children.get(name);
      directory.fileCount += 1;
      directory.totalSize += size;
    }
  }

  const finalize = (node) => ({
    ...node,
    children: [...node.children.values()]
      .map(finalize)
      .sort((a, b) => b.fileCount - a.fileCount || a.name.localeCompare(b.name))
  });

  return finalize(root);
}
