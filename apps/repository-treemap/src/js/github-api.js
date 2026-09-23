const API_ROOT = "https://api.github.com";

async function getJson(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/vnd.github+json" }
  });
  if (!response.ok) {
    throw new Error(`GitHub API ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchBranchTree(owner, repository, branch) {
  const commit = await getJson(`${API_ROOT}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/commits/${encodeURIComponent(branch)}`);
  const treeSha = commit?.commit?.tree?.sha;
  if (!treeSha) throw new Error(`Unable to resolve tree for ${branch}`);

  const result = await getJson(`${API_ROOT}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/git/trees/${treeSha}?recursive=1`);
  if (result.truncated) {
    throw new Error(`GitHub returned a truncated tree for ${branch}`);
  }
  return result.tree ?? [];
}
