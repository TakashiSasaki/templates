export const PREFERENCES_STORAGE_KEY = "repository-treemap.preferences.v1";

function normalizedStoredDepth(value) {
  if (value === "all") return "all";
  if (Number.isInteger(value) && value >= 1) return value;
  return null;
}

export function loadPreferences(storage, branches) {
  const allowedBranches = new Set(branches);
  const fallback = { lastBranch: null, relativeDepthByBranch: {} };
  if (!storage) return fallback;

  try {
    const serialized = storage.getItem(PREFERENCES_STORAGE_KEY);
    if (!serialized) return fallback;
    const parsed = JSON.parse(serialized);
    if (!parsed || typeof parsed !== "object") return fallback;

    const lastBranch = allowedBranches.has(parsed.lastBranch) ? parsed.lastBranch : null;
    const relativeDepthByBranch = {};
    const sourceDepths = parsed.relativeDepthByBranch;
    if (sourceDepths && typeof sourceDepths === "object") {
      for (const [branch, value] of Object.entries(sourceDepths)) {
        if (!allowedBranches.has(branch)) continue;
        const normalized = normalizedStoredDepth(value);
        if (normalized !== null) relativeDepthByBranch[branch] = normalized;
      }
    }
    return { lastBranch, relativeDepthByBranch };
  } catch {
    return fallback;
  }
}

export function savePreferences(storage, preferences) {
  if (!storage) return false;
  try {
    storage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
    return true;
  } catch {
    return false;
  }
}

export function withLastBranch(preferences, branch) {
  return {
    ...preferences,
    lastBranch: branch
  };
}

export function withBranchRelativeDepth(preferences, branch, depth) {
  const encodedDepth = depth === Infinity ? "all" : Math.max(1, Math.floor(depth));
  return {
    ...preferences,
    relativeDepthByBranch: {
      ...preferences.relativeDepthByBranch,
      [branch]: encodedDepth
    }
  };
}

export function relativeDepthForBranch(preferences, branch, fallbackDepth) {
  const stored = preferences.relativeDepthByBranch?.[branch];
  if (stored === "all") return Infinity;
  if (Number.isInteger(stored) && stored >= 1) return stored;
  return fallbackDepth;
}
