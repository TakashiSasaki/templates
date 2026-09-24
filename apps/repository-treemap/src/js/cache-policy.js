export const GITHUB_CACHE_TTL_MS = 30 * 60 * 1000;

export function isCacheTimestampFresh(cachedAt, now = Date.now(), ttlMs = GITHUB_CACHE_TTL_MS) {
  if (!Number.isFinite(cachedAt) || !Number.isFinite(now) || !Number.isFinite(ttlMs) || ttlMs <= 0) return false;
  const age = now - cachedAt;
  return age >= 0 && age < ttlMs;
}
