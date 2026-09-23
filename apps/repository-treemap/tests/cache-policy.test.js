import test from "node:test";
import assert from "node:assert/strict";
import { GITHUB_CACHE_TTL_MS, isCacheTimestampFresh } from "../src/js/cache-policy.js";
import { branchCommitUrl, recursiveTreeUrl, isGitHubRepositoryApiUrl } from "../src/js/github-api-urls.js";

test("GitHub cache TTL is exactly 30 minutes", () => {
  assert.equal(GITHUB_CACHE_TTL_MS, 30 * 60 * 1000);
});
test("cache is fresh before TTL and stale at TTL boundary", () => {
  const now = 2_000_000;
  assert.equal(isCacheTimestampFresh(now - GITHUB_CACHE_TTL_MS + 1, now), true);
  assert.equal(isCacheTimestampFresh(now - GITHUB_CACHE_TTL_MS, now), false);
});
test("future or invalid timestamps are not fresh", () => {
  assert.equal(isCacheTimestampFresh(2001, 2000), false);
  assert.equal(isCacheTimestampFresh(NaN, 2000), false);
});
test("GitHub API URL helpers create and recognize repository URLs", () => {
  const commit = branchCommitUrl("TakashiSasaki", "templates", "site");
  const tree = recursiveTreeUrl("TakashiSasaki", "templates", "abc123");
  assert.equal(commit, "https://api.github.com/repos/TakashiSasaki/templates/commits/site");
  assert.equal(tree, "https://api.github.com/repos/TakashiSasaki/templates/git/trees/abc123?recursive=1");
  assert.equal(isGitHubRepositoryApiUrl(commit), true);
  assert.equal(isGitHubRepositoryApiUrl("https://example.com/repos/a/b"), false);
});
