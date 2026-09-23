const API_ROOT = "https://api.github.com";

function repositoryBase(owner, repository) {
  return `${API_ROOT}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

export function branchCommitUrl(owner, repository, branch) {
  return `${repositoryBase(owner, repository)}/commits/${encodeURIComponent(branch)}`;
}

export function recursiveTreeUrl(owner, repository, treeSha) {
  return `${repositoryBase(owner, repository)}/git/trees/${encodeURIComponent(treeSha)}?recursive=1`;
}

export function isGitHubRepositoryApiUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "api.github.com" && url.pathname.startsWith("/repos/");
  } catch {
    return false;
  }
}
