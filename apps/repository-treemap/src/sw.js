import { GITHUB_CACHE_TTL_MS, isCacheTimestampFresh } from "./js/cache-policy.js";
import { branchCommitUrl, recursiveTreeUrl, isGitHubRepositoryApiUrl } from "./js/github-api-urls.js";

const CACHE_NAME = "repository-treemap-github-v1";
const CACHE_PREFIX = "repository-treemap-github-";
const META_BASE = new URL("./__github_cache_meta__", self.registration.scope);
const inFlight = new Map();

function apiRequest(url) {
  return new Request(url, { headers: { Accept: "application/vnd.github+json" } });
}

function metadataRequest(url) {
  const meta = new URL(META_BASE);
  meta.searchParams.set("url", url);
  return new Request(meta);
}

async function readCachedAt(cache, url) {
  const response = await cache.match(metadataRequest(url));
  if (!response) return NaN;
  return Number(await response.text());
}

async function deleteCached(cache, request) {
  await Promise.all([cache.delete(request), cache.delete(metadataRequest(request.url))]);
}

async function freshCachedResponse(cache, request) {
  const cached = await cache.match(request);
  if (!cached) return null;
  const cachedAt = await readCachedAt(cache, request.url);
  if (isCacheTimestampFresh(cachedAt)) return cached;
  await deleteCached(cache, request);
  return null;
}

async function fetchAndCache(cache, request) {
  if (!inFlight.has(request.url)) {
    const task = (async () => {
      const response = await fetch(request);
      if (response.ok) {
        await Promise.all([
          cache.put(request, response.clone()),
          cache.put(metadataRequest(request.url), new Response(String(Date.now()), {
            headers: { "Content-Type": "text/plain; charset=utf-8" }
          }))
        ]);
      }
      return response;
    })().finally(() => inFlight.delete(request.url));
    inFlight.set(request.url, task);
  }
  return (await inFlight.get(request.url)).clone();
}

async function cachedFetch(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await freshCachedResponse(cache, request);
  if (cached) return cached;
  return fetchAndCache(cache, request);
}

async function prefetchBranch(cache, owner, repository, branch) {
  const commitRequest = apiRequest(branchCommitUrl(owner, repository, branch));
  const commitResponse = (await freshCachedResponse(cache, commitRequest)) || await fetchAndCache(cache, commitRequest);
  if (!commitResponse.ok) return;
  const commit = await commitResponse.clone().json();
  const treeSha = commit?.commit?.tree?.sha;
  if (!treeSha) return;
  const treeRequest = apiRequest(recursiveTreeUrl(owner, repository, treeSha));
  if (!(await freshCachedResponse(cache, treeRequest))) await fetchAndCache(cache, treeRequest);
}

async function pruneExpired(cache) {
  const keys = await cache.keys();
  const metaPrefix = META_BASE.href;
  for (const request of keys) {
    if (!request.url.startsWith(metaPrefix)) continue;
    const cachedAt = Number(await (await cache.match(request)).text());
    if (isCacheTimestampFresh(cachedAt)) continue;
    const originalUrl = new URL(request.url).searchParams.get("url");
    if (originalUrl) await cache.delete(originalUrl);
    await cache.delete(request);
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || !isGitHubRepositoryApiUrl(event.request.url)) return;
  event.respondWith(cachedFetch(event.request));
});

self.addEventListener("message", (event) => {
  const data = event.data;
  if (data?.type !== "prefetch-github-repository") return;
  const owner = typeof data.owner === "string" ? data.owner : "";
  const repository = typeof data.repository === "string" ? data.repository : "";
  const branches = Array.isArray(data.branches) ? data.branches.filter((branch) => typeof branch === "string") : [];
  if (!owner || !repository || !branches.length) return;

  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await pruneExpired(cache);
    await Promise.allSettled(branches.map((branch) => prefetchBranch(cache, owner, repository, branch)));
  })());
});

export { GITHUB_CACHE_TTL_MS };
