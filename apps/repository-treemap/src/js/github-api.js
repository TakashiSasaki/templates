import { branchCommitUrl, recursiveTreeUrl } from "./github-api-urls.js";

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
  if (!response.ok) throw new Error(`GitHub API ${response.status}: ${response.statusText}`);
  return response.json();
}

export async function fetchBranchTree(owner, repository, branch) {
  const commit = await getJson(branchCommitUrl(owner, repository, branch));
  const treeSha = commit?.commit?.tree?.sha;
  if (!treeSha) throw new Error(`Unable to resolve tree for ${branch}`);
  const result = await getJson(recursiveTreeUrl(owner, repository, treeSha));
  if (result.truncated) throw new Error(`GitHub returned a truncated tree for ${branch}`);
  return result.tree ?? [];
}
