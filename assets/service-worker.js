const CACHE_NAME = "templates-portal-shell-v4";
const DOCUMENT_CACHE_NAME = "templates-portal-documents-v1";
const STATIC_ASSETS = [
  "/app.webmanifest",
  "/icon.svg",
  "/stylesheets/extra.css",
  "/stylesheets/landing-cover.css",
  "/stylesheets/landing-shell.css",
  "/stylesheets/mobile-density.css",
  "/stylesheets/translation-reader.css",
  "/stylesheets/glossary-inline.css",
  "/stylesheets/freshness-status.css",
  "/javascripts/repository-tree-viewer.js",
  "/javascripts/repository-browser.js",
  "/javascripts/guided-copy.js",
  "/javascripts/pwa.js",
  "/javascripts/glossary-inline.js"
];
const FRESHNESS_STATES = Object.freeze([
  "verified-current",
  "checking",
  "cached-unverified",
  "update-available",
]);
const CACHED_DOCUMENT_NOTICE =
  '<aside id="templates-freshness-status" ' +
  'class="freshness-status freshness-status--cached" ' +
  'data-freshness-state="cached-unverified" role="status" aria-live="polite">' +
  '<strong>Saved copy.</strong> The latest version could not be verified.' +
  "</aside>";
const FRESHNESS_UI_ACK_TIMEOUT_MS = 500;
const documentCacheMutationQueues = new Map();

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

  const accept = request.headers.get("Accept") || "";
  if (accept.toLowerCase().includes("text/html")) {
    return true;
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

function isCacheableDocumentResponse(response) {
  if (response.status !== 200) {
    return false;
  }
  if (!response.url) {
    return false;
  }
  try {
    if (new URL(response.url).origin !== self.location.origin) {
      return false;
    }
  } catch (error) {
    console.warn("PWA document response URL is invalid", error);
    return false;
  }
  const contentType = response.headers.get("Content-Type") || "";
  return contentType.toLowerCase().includes("text/html");
}

function enqueueDocumentCacheMutation(request, operation) {
  const key = request.url;
  const previous = documentCacheMutationQueues.get(key) || Promise.resolve();
  const next = previous.catch(() => undefined).then(operation);
  documentCacheMutationQueues.set(key, next);
  return next.finally(() => {
    if (documentCacheMutationQueues.get(key) === next) {
      documentCacheMutationQueues.delete(key);
    }
  });
}

async function cacheVerifiedDocument(request, cachedResponse) {
  try {
    await enqueueDocumentCacheMutation(request, async () => {
      const cache = await caches.open(DOCUMENT_CACHE_NAME);
      await cache.put(request, cachedResponse);
    });
  } catch (error) {
    console.warn("PWA document cache update failed", error);
  }
}

async function deleteCachedDocument(request) {
  await enqueueDocumentCacheMutation(request, async () => {
    const cache = await caches.open(DOCUMENT_CACHE_NAME);
    await cache.delete(request);
  });
}

async function decorateCachedDocument(response, request) {
  const contentType = response.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().includes("text/html")) {
    return undefined;
  }

  if (response.url && response.url !== request.url) {
    console.warn("PWA cached redirect fallback rejected", response.url, request.url);
    return undefined;
  }

  let source;
  try {
    source = await response.text();
  } catch (error) {
    console.warn("PWA cached document read failed", error);
    return undefined;
  }

  const decorated = source + CACHED_DOCUMENT_NOTICE;
  const headers = new Headers(response.headers);
  for (const name of ["Content-Encoding", "Content-Length", "ETag", "Last-Modified"]) {
    headers.delete(name);
  }
  headers.set("Cache-Control", "no-store");
  headers.set("X-Templates-Freshness", "cached-unverified");
  return new Response(decorated, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function cachedDocumentFallback(request) {
  try {
    const cache = await caches.open(DOCUMENT_CACHE_NAME);
    const response = await cache.match(request);
    if (!response) {
      return undefined;
    }
    return await decorateCachedDocument(response, request);
  } catch (error) {
    console.warn("PWA document cache lookup failed", error);
    return undefined;
  }
}

async function notifyInstantNavigationState(event, state, requireAcknowledgement = false) {
  if (event.request.mode === "navigate") {
    return true;
  }
  if (!event.clientId) {
    return !requireAcknowledgement;
  }

  let client;
  try {
    client = await self.clients.get(event.clientId);
  } catch (error) {
    console.warn("PWA freshness client lookup failed", error);
    return !requireAcknowledgement;
  }
  if (!client || typeof client.postMessage !== "function") {
    return !requireAcknowledgement;
  }

  const message = {
    type: "templates:freshness-state",
    state,
    url: event.request.url,
  };
  if (!requireAcknowledgement) {
    client.postMessage(message);
    return true;
  }

  return await new Promise((resolve) => {
    const channel = new MessageChannel();
    let settled = false;
    const finish = (acknowledged) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      channel.port1.close();
      resolve(acknowledged);
    };
    const timer = setTimeout(() => finish(false), FRESHNESS_UI_ACK_TIMEOUT_MS);
    channel.port1.onmessage = (messageEvent) => {
      const data = messageEvent.data;
      finish(
        data?.type === "templates:freshness-state-applied" &&
          data.state === state
      );
    };
    try {
      client.postMessage(message, [channel.port2]);
    } catch (error) {
      console.warn("PWA freshness state notification failed", error);
      finish(false);
    }
  });
}

async function fetchDocumentNetworkFirst(event) {
  const request = event.request;
  try {
    const response = await fetchFreshDocument(request);
    if (response.status === 404 || response.status === 410) {
      try {
        await deleteCachedDocument(request);
      } catch (error) {
        console.warn("PWA authoritative document cache deletion failed", error);
        try {
          await caches.delete(DOCUMENT_CACHE_NAME);
        } catch (cleanupError) {
          console.warn("PWA document cache namespace cleanup failed", cleanupError);
        }
      }
      return response;
    }
    if (response.status >= 500) {
      const cached = await cachedDocumentFallback(request);
      if (!cached) {
        return response;
      }
      if (
        !(await notifyInstantNavigationState(event, "cached-unverified", true))
      ) {
        return response;
      }
      return cached;
    }
    if (isCacheableDocumentResponse(response)) {
      const cachedResponse = response.clone();
      event.waitUntil(cacheVerifiedDocument(request, cachedResponse));
    }
    return response;
  } catch (error) {
    const cached = await cachedDocumentFallback(request);
    if (!cached) {
      return offlineResponse();
    }
    if (
      !(await notifyInstantNavigationState(event, "cached-unverified", true))
    ) {
      return offlineResponse();
    }
    return cached;
  }
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
    event.respondWith(fetchDocumentNetworkFirst(event));
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
