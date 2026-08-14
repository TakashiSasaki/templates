const CACHE_NAME = "templates-portal-shell-v2";
const STATIC_ASSETS = ["/app.webmanifest", "/icon.svg"];

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

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (isDocumentRequest(event.request, url)) {
    if (event.request.mode === "navigate") {
      event.respondWith(fetchFreshDocument(event.request).catch(() => offlineResponse()));
    } else {
      event.respondWith(fetchFreshDocument(event.request));
    }
    return;
  }

  if (STATIC_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches
        .open(CACHE_NAME)
        .then((cache) => cache.match(event.request, { ignoreSearch: true }))
        .then((cached) => cached || fetch(event.request))
        .catch(() => offlineResponse())
    );
  }
});
