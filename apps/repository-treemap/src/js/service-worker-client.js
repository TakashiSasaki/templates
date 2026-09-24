export async function registerRepositoryTreemapServiceWorker() {
  if (!("serviceWorker" in navigator)) return null;
  try {
    const registration = await navigator.serviceWorker.register("./sw.js", { type: "module", scope: "./" });
    await navigator.serviceWorker.ready;
    return registration;
  } catch (error) {
    console.warn("Service worker registration failed", error);
    return null;
  }
}

export function requestGitHubPrefetch(registration, config) {
  if (!registration) return;
  const worker = navigator.serviceWorker.controller || registration.active || registration.waiting;
  worker?.postMessage({
    type: "prefetch-github-repository",
    owner: config.owner,
    repository: config.repository,
    branches: config.branches
  });
}
