const CACHE_NAME = "templates-portal-shell-v3";
const DOCUMENT_CACHE_NAME = "templates-portal-documents-v1";
const STATIC_ASSETS = ["/app.webmanifest", "/icon.svg"];
const FRESHNESS_STATES = Object.freeze([
  "verified-current",
  "checking",
  "cached-unverified",
  "update-available",
]);

function offlineResponse() {
  return new Response("This page is unavailable while offline.\n", {
    status: 503,
    statusText: "Service Unavailable",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

function isDocumentRequest(request, url) {
  if (request.mode === "navigate") {
    return true;
  }

  if (request.destination !== "") {
    return false;
  }

  const pathname = url.pathname;
  if (pathname.endsWith("/") || pathname.endsWith(".html")) {
    return true;
  }

  const lastSegment = pathname.slice(pathname.lastIndexOf("/") + 1);
  return lastSegment.length > 0 && !lastSegment.includes(".");
}

function fetchFreshDocument(request) {
  return fetch(request, { cache: "no-cache" });
}

async function refreshStaticAsset(request) {
  const response = await fetch(request, { cache: "no-cache" });
  if (response.ok) {
    try {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, response.clone());
    } catch (error) {
      console.warn("PWA static asset cache refresh failed", error);
    }
  }
  return response;
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("templates-portal-shell-") && key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (
    event.data?.type !== "templates:get-freshness-capabilities" ||
    !event.source ||
    typeof event.source.postMessage !== "function"
  ) {
    return;
  }
  event.source.postMessage({
    type: "templates:freshness-capabilities",
    states: FRESHNESS_STATES,
    siteVersionUrl: "/site-version.json",
    documentCacheName: DOCUMENT_CACHE_NAME,
  });
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (isDocumentRequest(event.request, url)) {
    event.respondWith(fetchFreshDocument(event.request).catch(() => offlineResponse()));
    return;
  }

  if (STATIC_ASSETS.includes(url.pathname)) {
    const refresh = refreshStaticAsset(event.request);
    const cached = caches
      .open(CACHE_NAME)
      .then((cache) => cache.match(event.request))
      .catch(() => undefined);
    event.waitUntil(refresh.catch(() => undefined));
    event.respondWith(
      cached
        .then((response) => response || refresh)
        .catch(() => offlineResponse())
    );
  }
});
